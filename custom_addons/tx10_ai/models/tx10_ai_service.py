import json
import logging
from datetime import datetime

import httpx

from odoo import models

_logger = logging.getLogger(__name__)


class Tx10AiService(models.AbstractModel):
    _name = "tx10.ai.service"
    _description = "TX10 AI LLM Service (OpenRouter)"

    def _get_config(self, key, default=None):
        return (
            self.env["ir.config_parameter"].sudo().get_param(f"tx10_ai.{key}", default)
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
            "HTTP-Referer": "https://tx10.team",
            "X-Title": "TX10 Odoo AI",
        }

    def chat(self, messages, model=None, tools=None, timeout=30):
        """Send a chat completion request to OpenRouter.

        Returns {'content': str, 'usage': dict, 'elapsed_ms': int} or error dict.
        """
        headers = self._build_headers()
        if not headers:
            _logger.warning(
                "tx10_ai: no OpenRouter API key configured — skipping LLM call",
            )
            return {"content": "", "usage": {}, "error": "no_api_key", "error_code": "no_api_key"}

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
                "tx10_ai: OpenRouter HTTP error %s: %s",
                exc.response.status_code,
                exc.response.text[:300],
            )
            return {"content": "", "usage": {}, "error": str(exc), "error_code": "http_error"}
        except httpx.RequestError as exc:
            _logger.error("tx10_ai: OpenRouter request error: %s", exc)
            return {"content": "", "usage": {}, "error": str(exc), "error_code": "network_error"}

        data = resp.json()
        elapsed_ms = int((datetime.now() - started_at).total_seconds() * 1000)
        _logger.info(
            "tx10_ai: LLM call complete in %dms (model=%s)",
            elapsed_ms,
            model,
        )

        choices = data.get("choices") or []
        if not choices:
            _logger.warning(
                "tx10_ai: empty choices in response (model=%s) — likely safety filter",
                model,
            )
            return {
                "content": "",
                "usage": data.get("usage", {}),
                "elapsed_ms": elapsed_ms,
                "error": "empty_choices",
                "error_code": "empty_choices",
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
                "error_code": "no_api_key",
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
                "tx10_ai: OpenRouter HTTP error %s: %s",
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
                "error_code": "http_error",
            }
        except httpx.RequestError as exc:
            _logger.error("tx10_ai: OpenRouter request error: %s", exc)
            return {
                "content": "",
                "tool_calls": [],
                "finish_reason": "error",
                "usage": {},
                "elapsed_ms": 0,
                "error": str(exc),
                "error_code": "network_error",
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
                "error_code": "empty_choices",
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
                    "tx10_ai: could not parse tool_call args for %s: %s",
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
            result["error_code"] = f"terminated_{finish_reason}"
        return result

    def classify_document_text(self, text, filename="", types=None):
        """Classify a document using LLM. Returns {document_type_code, confidence, reasons}."""
        if types is None:
            types = self.env["solar.document.type"].sudo().search([("active", "=", True)])

        type_lines = "\n".join(
            f'- code="{t.code}" | {t.name}{(": " + t.description) if t.description else ""}'
            for t in types
        )

        system_msg = (
            "You are a document classification assistant for a solar energy company. "
            "Classify the given document into exactly one of the available types. "
            'Respond ONLY with valid JSON: {"document_type_code": "...", "confidence": 0.0-1.0, "reasons": ["..."]}. '
            'Use document_type_code="unknown" if you are unsure or confidence is below 0.70.'
        )
        user_msg = (
            f"Available document types:\n{type_lines}\n\n"
            f"Filename: {filename or '(unknown)'}\n"
            f"Text excerpt:\n{text[:3000] if text else '(no extractable text)'}\n\n"
            "Classify this document."
        )

        response = self.chat(
            messages=[
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_msg},
            ],
            timeout=30,
        )

        if response.get("error"):
            _logger.warning("tx10_ai: classify_document_text LLM error: %s", response["error"])
            return {"document_type_code": "unknown", "confidence": 0.0, "reasons": [response.get("error", "llm_error")]}

        content = response.get("content", "")
        # Strip markdown code fences if present
        if "```" in content:
            parts = content.split("```")
            content = parts[1] if len(parts) > 1 else content
            if content.startswith("json"):
                content = content[4:]

        try:
            parsed = json.loads(content.strip())
            if not isinstance(parsed.get("confidence"), (int, float)):
                raise TypeError  # noqa: TRY301
            return parsed
        except (TypeError, json.JSONDecodeError):
            _logger.warning("tx10_ai: classify_document_text parse error, raw: %s", content[:300])
            return {"document_type_code": "unknown", "confidence": 0.0, "reasons": ["parse_error"]}
