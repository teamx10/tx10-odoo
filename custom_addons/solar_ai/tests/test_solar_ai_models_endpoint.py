import json
import time
from unittest.mock import MagicMock, patch

import httpx

from odoo.tests import TransactionCase, tagged

_SAMPLE_OPENROUTER_RESPONSE = {
    "data": [
        {
            "id": "anthropic/claude-3.5-haiku",
            "name": "Claude 3.5 Haiku",
            "pricing": {"prompt": "0.0000008", "completion": "0.000004"},
        },
        {
            "id": "openai/gpt-4o",
            "name": "GPT-4o",
            "pricing": {"prompt": "0.0000025", "completion": "0.00001"},
        },
    ],
}

_EXPECTED_MODELS = [
    {
        "id": "anthropic/claude-3.5-haiku",
        "name": "Claude 3.5 Haiku",
        "provider": "Anthropic",
        "pricing_in": 0.80,
        "pricing_out": 4.00,
    },
    {
        "id": "openai/gpt-4o",
        "name": "GPT-4o",
        "provider": "Openai",
        "pricing_in": 2.50,
        "pricing_out": 10.00,
    },
]


def _make_mock_response(data):
    mock = MagicMock()
    mock.raise_for_status = MagicMock()
    mock.json.return_value = data
    return mock


@tagged("post_install", "-at_install")
class TestSolarAiModelsEndpoint(TransactionCase):
    """Unit tests for the OpenRouter models proxy + cache logic."""

    def setUp(self):
        super().setUp()
        param = self.env["ir.config_parameter"].sudo()
        param.search(
            [("key", "in", ["solar_ai.models_cache", "solar_ai.models_cache_ts"])],
        ).unlink()

    def _get_service(self):
        from odoo.addons.solar_ai.controllers import (  # noqa: PLC0415
            openrouter_models as _m,
        )

        ctrl = _m.SolarAiModelsController()
        ctrl.env = self.env
        return ctrl

    def test_models_endpoint_returns_normalised_list(self):
        """Fetched data is normalised to our contract shape."""
        ctrl = self._get_service()
        with patch("httpx.get", return_value=_make_mock_response(_SAMPLE_OPENROUTER_RESPONSE)):
            result = ctrl._fetch_and_cache(self.env)
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["id"], "anthropic/claude-3.5-haiku")
        self.assertEqual(result[0]["provider"], "Anthropic")
        self.assertAlmostEqual(result[0]["pricing_in"], 0.80, places=4)
        self.assertAlmostEqual(result[0]["pricing_out"], 4.00, places=4)

    def test_cache_hit_skips_http(self):
        """Second call within TTL reads from ir.config_parameter, no HTTP."""
        param = self.env["ir.config_parameter"].sudo()
        param.set_param("solar_ai.models_cache", json.dumps(_EXPECTED_MODELS))
        param.set_param("solar_ai.models_cache_ts", str(int(time.time())))

        ctrl = self._get_service()
        with patch("httpx.get") as mock_get:
            result, was_cached = ctrl._get_models(self.env)
            mock_get.assert_not_called()
        self.assertEqual(len(result), 2)
        self.assertTrue(was_cached)

    def test_cache_expired_refetches(self):
        """Stale cache (> 24 h) triggers a fresh HTTP request and was_cached is False."""
        param = self.env["ir.config_parameter"].sudo()
        param.set_param("solar_ai.models_cache", json.dumps(_EXPECTED_MODELS))
        param.set_param("solar_ai.models_cache_ts", str(int(time.time()) - 90_000))

        ctrl = self._get_service()
        with patch(
            "httpx.get", return_value=_make_mock_response(_SAMPLE_OPENROUTER_RESPONSE),
        ) as mock_get:
            _result, was_cached = ctrl._get_models(self.env)
            mock_get.assert_called_once()
        self.assertFalse(was_cached)

    def test_fallback_returns_stale_cache_on_network_error(self):
        """Network error with stale cache → return stale data, was_cached True, no exception."""
        param = self.env["ir.config_parameter"].sudo()
        param.set_param("solar_ai.models_cache", json.dumps(_EXPECTED_MODELS))
        param.set_param("solar_ai.models_cache_ts", str(int(time.time()) - 90_000))

        ctrl = self._get_service()
        with patch("httpx.get", side_effect=httpx.RequestError("timeout")):
            result, was_cached = ctrl._get_models(self.env)
        self.assertEqual(len(result), 2, "Must return stale cache on network error")
        self.assertTrue(was_cached)

    def test_fallback_returns_empty_on_no_cache_and_error(self):
        """Network error with no cache at all → return empty list, was_cached False, no exception."""
        ctrl = self._get_service()
        with patch("httpx.get", side_effect=httpx.RequestError("timeout")):
            result, was_cached = ctrl._get_models(self.env)
        self.assertEqual(result, [], "Must return [] when no cache and network fails")
        self.assertFalse(was_cached)

    def test_pricing_normalised_to_per_million(self):
        """pricing.prompt=0.0000008 must become pricing_in=0.80 (per 1M tokens)."""
        ctrl = self._get_service()
        raw = {
            "data": [
                {
                    "id": "x/y",
                    "name": "Y",
                    "pricing": {"prompt": "0.0000008", "completion": "0.000004"},
                },
            ],
        }
        with patch("httpx.get", return_value=_make_mock_response(raw)):
            result = ctrl._fetch_and_cache(self.env)
        self.assertAlmostEqual(result[0]["pricing_in"], 0.80, places=4)
        self.assertAlmostEqual(result[0]["pricing_out"], 4.00, places=4)

    def test_free_tier_pricing_yields_zero(self):
        """OpenRouter returns 'free' for zero-cost models — must not raise ValueError."""
        ctrl = self._get_service()
        raw = {
            "data": [
                {
                    "id": "meta-llama/llama-3.1-8b-instruct:free",
                    "name": "Llama 3.1 8B (free)",
                    "pricing": {"prompt": "free", "completion": "free"},
                },
            ],
        }
        with patch("httpx.get", return_value=_make_mock_response(raw)):
            result = ctrl._fetch_and_cache(self.env)
        self.assertEqual(result[0]["pricing_in"], 0.0)
        self.assertEqual(result[0]["pricing_out"], 0.0)

    def test_http_status_error_falls_back_to_stale_cache(self):
        """OpenRouter 4xx/5xx (HTTPStatusError) → return stale cache, no 500."""
        # TODO: implement this test
        # Context: _get_models catches (RequestError, HTTPStatusError).
        # HTTPStatusError is raised by resp.raise_for_status() when OpenRouter returns
        # 401/429/500. This branch was previously uncaught → server 500.
        #
        # Hint: httpx.HTTPStatusError requires (message, request=..., response=...).
        # Build a mock request and response so the constructor doesn't raise.
        # Then side_effect the mock so _fetch_and_cache → raise_for_status raises it.
        #
        # Assert: result has stale models (len == 2) and was_cached is True.
        param = self.env["ir.config_parameter"].sudo()
        param.set_param("solar_ai.models_cache", json.dumps(_EXPECTED_MODELS))
        param.set_param("solar_ai.models_cache_ts", str(int(time.time()) - 90_000))

        ctrl = self._get_service()  # noqa: F841
        # YOUR CODE HERE (~7 lines):
        # 1. Build an httpx.HTTPStatusError with mock request + response
        # 2. Patch httpx.get to raise it
        # 3. Call ctrl._get_models(self.env) and unpack the tuple
        # 4. Assert len(result) == 2 and was_cached is True
        msg = "test_http_status_error_falls_back_to_stale_cache not implemented"
        raise NotImplementedError(msg)
