import json
import logging
from datetime import datetime

import httpx

from odoo import models

_logger = logging.getLogger(__name__)

CLASSIFICATION_SYSTEM_PROMPT = """You are a document classifier for solar energy installation projects.
Given document text, classify it into one of the following types and return JSON:
{"document_type_code": "<code>", "confidence": <0.0-1.0>, "extracted_summary": "<brief summary>"}

Document type codes:
- bill_electricity: electricity consumption bill
- roof_measurement: roof measurement or survey report
- site_plan_bti: site plan, BTI (Bureau of Technical Inventory) scheme
- topographic_survey: topographic survey map
- client_brief: client requirements or technical brief
- equipment_spec: equipment datasheet or specification
- single_line_diagram: electrical single-line or wiring diagram
- permit: building or grid connection permit
- handover_act: handover or acceptance act
- commissioning_report: commissioning or testing report
- structural_calculation: structural engineering calculation
- grid_connection_agreement: grid connection agreement
- unknown: none of the above

Respond with ONLY the JSON object, no markdown fences."""


class SolarAiService(models.AbstractModel):
    _name = "solar.ai.service"
    _description = "Solar AI LLM Service (OpenRouter)"

    def _get_config(self, key, default=None):
        return (
            self.env["ir.config_parameter"].sudo().get_param(f"solar_ai.{key}", default)
        )

    def _resolve_model(self, model):
        """Resolve the model id, treating a blank default_model the same as absent.

        ir.config_parameter keeps an empty string rather than deleting the param, so a
        get_param default only fires when the key is missing. Chaining `or` makes a blank
        value fall back to the hardcoded default instead of sending model='' to OpenRouter.
        """
        return (
            model or self._get_config("default_model") or "anthropic/claude-sonnet-4-5"
        )

    def _build_headers(self):
        api_key = self._get_config("openrouter_api_key")
        if not api_key:
            return None
        return {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://isolar.ua",
            "X-Title": "iSolar Odoo",
        }

    def chat(self, messages, model=None, tools=None, timeout=30):
        """Send a chat completion request to OpenRouter.

        Returns {'content': str, 'usage': dict, 'elapsed_ms': int} or error dict.
        """
        headers = self._build_headers()
        if not headers:
            _logger.warning(
                "solar_ai: no OpenRouter API key configured — skipping LLM call",
            )
            return {"content": "", "usage": {}}

        base_url = self._get_config(
            "openrouter_base_url",
            "https://openrouter.ai/api/v1",
        )
        model = self._resolve_model(model)

        payload = {"model": model, "messages": messages}
        if tools:
            payload["tools"] = tools

        started_at = datetime.now()
        try:
            resp = httpx.post(
                f"{base_url}/chat/completions",
                headers=headers,
                json=payload,
                timeout=timeout,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            _logger.error(
                "solar_ai: OpenRouter HTTP error %s: %s",
                exc.response.status_code,
                exc.response.text[:300],
            )
            return {"content": "", "usage": {}, "error": str(exc)}
        except httpx.RequestError as exc:
            _logger.error("solar_ai: OpenRouter request error: %s", exc)
            return {"content": "", "usage": {}, "error": str(exc)}

        data = resp.json()
        elapsed_ms = int((datetime.now() - started_at).total_seconds() * 1000)
        _logger.info(
            "solar_ai: LLM call complete in %dms (model=%s)",
            elapsed_ms,
            model,
        )

        choices = data.get("choices") or []
        if not choices:
            _logger.warning(
                "solar_ai: empty choices in response (model=%s) — likely safety filter",
                model,
            )
            return {
                "content": "",
                "usage": data.get("usage", {}),
                "elapsed_ms": elapsed_ms,
                "error": "empty_choices",
            }
        content = (choices[0].get("message") or {}).get("content") or ""
        return {
            "content": content,
            "usage": data.get("usage", {}),
            "elapsed_ms": elapsed_ms,
        }

    def chat_with_tools(self, messages, tools=None, model=None, timeout=25):
        """LLM round-trip that parses tool_calls from the response.

        Returns:
            {
                "content": str | None,
                "tool_calls": list[{id, name, arguments_str, parsed_args, parse_error?}],
                "finish_reason": str,
                "usage": dict,
                "elapsed_ms": int,
                "error": str,  # present on terminal errors
            }
        """
        headers = self._build_headers()
        if not headers:
            return {
                "content": "",
                "tool_calls": [],
                "finish_reason": "error",
                "usage": {},
                "elapsed_ms": 0,
                "error": "no_api_key",
            }

        model = self._resolve_model(model)
        payload = {"model": model, "messages": messages}
        if tools:
            payload["tools"] = tools

        started = datetime.now()
        try:
            resp = httpx.post(
                self._get_config("openrouter_base_url", "https://openrouter.ai/api/v1")
                + "/chat/completions",
                headers=headers,
                json=payload,
                timeout=timeout,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            _logger.error(
                "solar_ai: OpenRouter HTTP error %s: %s",
                exc.response.status_code,
                exc.response.text[:300],
            )
            return {
                "content": "",
                "tool_calls": [],
                "finish_reason": "error",
                "usage": {},
                "elapsed_ms": 0,
                "error": str(exc),
            }
        except httpx.RequestError as exc:
            _logger.error("solar_ai: OpenRouter request error: %s", exc)
            return {
                "content": "",
                "tool_calls": [],
                "finish_reason": "error",
                "usage": {},
                "elapsed_ms": 0,
                "error": str(exc),
            }

        elapsed_ms = int((datetime.now() - started).total_seconds() * 1000)
        data = resp.json()
        choices = data.get("choices") or []
        if not choices:
            return {
                "content": "",
                "tool_calls": [],
                "finish_reason": "error",
                "usage": data.get("usage", {}),
                "elapsed_ms": elapsed_ms,
                "error": "empty_choices",
            }

        choice = choices[0]
        message = choice.get("message") or {}
        finish_reason = choice.get("finish_reason", "stop")
        content = message.get("content")

        # Parse tool_calls — arguments is a JSON STRING from the model.
        # Do NOT store the raw tc object — not guaranteed JSON-serializable for fields.Json.
        raw_tool_calls = message.get("tool_calls") or []
        parsed_calls = []
        for tc in raw_tool_calls:
            func = tc.get("function") or {}
            entry = {
                "id": tc.get("id", ""),
                "name": func.get("name", ""),
                "arguments_str": func.get("arguments", "{}"),
            }
            try:
                entry["parsed_args"] = json.loads(func.get("arguments", "{}"))
            except (json.JSONDecodeError, TypeError) as exc:
                entry["parsed_args"] = None
                entry["parse_error"] = str(exc)
                _logger.warning(
                    "solar_ai: could not parse tool_call args for %s: %s",
                    entry["name"],
                    exc,
                )
            parsed_calls.append(entry)

        result = {
            "content": content,
            "tool_calls": parsed_calls,
            "finish_reason": finish_reason,
            "usage": data.get("usage", {}),
            "elapsed_ms": elapsed_ms,
        }
        if finish_reason in ("length", "content_filter"):
            result["error"] = f"terminated_{finish_reason}"
        return result

    def classify_document_text(self, text, max_chars=4000):
        """Classify document text, return dict with 'document_type_code' and 'confidence'."""
        truncated = text[:max_chars] if len(text) > max_chars else text
        messages = [
            {"role": "system", "content": CLASSIFICATION_SYSTEM_PROMPT},
            {"role": "user", "content": truncated},
        ]
        result = self.chat(messages)
        try:
            return json.loads(result["content"])
        except (json.JSONDecodeError, KeyError):
            return {"document_type_code": "unknown", "confidence": 0.0}
