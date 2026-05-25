import json
import logging
import time

import httpx

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)

_OPENROUTER_MODELS_URL = "https://openrouter.ai/api/v1/models"
_CACHE_KEY = "solar_ai.models_cache"
_CACHE_TS_KEY = "solar_ai.models_cache_ts"
_TTL_SECONDS = 86_400  # 24 hours


def _normalise(raw_model: dict) -> dict:
    model_id = raw_model.get("id", "")
    provider = model_id.split("/")[0].title() if "/" in model_id else "Other"
    pricing = raw_model.get("pricing") or {}
    return {
        "id": model_id,
        "name": raw_model.get("name") or model_id,
        "provider": provider,
        "pricing_in": round(float(pricing.get("prompt") or 0) * 1_000_000, 4),
        "pricing_out": round(float(pricing.get("completion") or 0) * 1_000_000, 4),
    }


class SolarAiModelsController(http.Controller):

    def _fetch_and_cache(self, env) -> list:
        resp = httpx.get(_OPENROUTER_MODELS_URL, timeout=10)
        resp.raise_for_status()
        data = resp.json().get("data", [])
        models = [_normalise(m) for m in data if m.get("id")]
        param = env["ir.config_parameter"].sudo()
        param.set_param(_CACHE_KEY, json.dumps(models))
        param.set_param(_CACHE_TS_KEY, str(int(time.time())))
        return models

    def _get_models(self, env) -> list:
        param = env["ir.config_parameter"].sudo()
        cached_json = param.get_param(_CACHE_KEY, "")
        cached_ts = int(param.get_param(_CACHE_TS_KEY, "0") or 0)
        cache_fresh = cached_json and (time.time() - cached_ts) < _TTL_SECONDS

        if cache_fresh:
            return json.loads(cached_json)

        try:
            return self._fetch_and_cache(env)
        except httpx.RequestError as exc:
            _logger.warning("solar_ai: failed to fetch OpenRouter models: %s", exc)
            if cached_json:
                return json.loads(cached_json)
            return []

    @http.route(
        "/solar_ai/openrouter/models",
        type="http",
        auth="user",
        methods=["GET"],
        csrf=False,
    )
    def get_models(self, **_kwargs):
        models = self._get_models(request.env)
        param = request.env["ir.config_parameter"].sudo()
        cached_ts = int(param.get_param(_CACHE_TS_KEY, "0") or 0)
        was_cached = (time.time() - cached_ts) < _TTL_SECONDS
        payload = json.dumps({"models": models, "cached": was_cached})
        return request.make_response(
            payload,
            headers=[("Content-Type", "application/json")],
        )
