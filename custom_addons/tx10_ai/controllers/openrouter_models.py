import json
import logging
import time

import httpx

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


def _safe_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


_OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
_CACHE_KEY = "tx10_ai.models_cache"
_CACHE_TS_KEY = "tx10_ai.models_cache_ts"
_TTL_SECONDS = 86_400  # 24 hours


def _normalise(raw_model: dict) -> dict:
    model_id = raw_model.get("id", "")
    provider = model_id.split("/")[0].title() if "/" in model_id else "Other"
    pricing = raw_model.get("pricing") or {}
    return {
        "id": model_id,
        "name": raw_model.get("name") or model_id,
        "provider": provider,
        "pricing_in": round(_safe_float(pricing.get("prompt")) * 1_000_000, 4),
        "pricing_out": round(_safe_float(pricing.get("completion")) * 1_000_000, 4),
    }


class Tx10AiModelsController(http.Controller):

    def _fetch_and_cache(self, env) -> list:
        resp = httpx.get(_OPENROUTER_MODELS_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json().get("data", [])
        models = [_normalise(m) for m in data if m.get("id")]
        param = env["ir.config_parameter"].sudo()
        param.set_param(_CACHE_KEY, json.dumps(models))
        param.set_param(_CACHE_TS_KEY, str(int(time.time())))
        return models

    def _get_models(self, env) -> tuple:
        param = env["ir.config_parameter"].sudo()
        cached_json = param.get_param(_CACHE_KEY, "")
        cached_ts = int(param.get_param(_CACHE_TS_KEY, "0") or 0)
        cache_fresh = cached_json and (time.time() - cached_ts) < _TTL_SECONDS

        if cache_fresh:
            return json.loads(cached_json), True

        try:
            return self._fetch_and_cache(env), False
        except (httpx.RequestError, httpx.HTTPStatusError) as exc:
            _logger.warning("tx10_ai: failed to fetch OpenRouter models: %s", exc)
            if cached_json:
                return json.loads(cached_json), True
            return [], False

    @http.route(
        "/tx10_ai/openrouter/models",
        type="http",
        auth="user",
        methods=["GET"],
        csrf=False,
    )
    def get_models(self, **_kwargs):
        models, was_cached = self._get_models(request.env)
        payload = json.dumps({"models": models, "cached": was_cached})
        return request.make_response(
            payload,
            headers=[("Content-Type", "application/json")],
        )
