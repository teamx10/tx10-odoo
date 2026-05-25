# Solar AI — Model Select Widget

**Date**: 2026-05-24
**Branch**: feat/solar-ai-model-select
**Status**: In progress

## Goal

Replace the free-text `Default Model` field in Settings → Solar AI Assistant with a
searchable combobox that shows all OpenRouter models grouped by provider, with
`$X.XX in / $X.XX out` pricing per 1M tokens. Free-typing is still allowed for
custom model IDs not in the list.

## Decisions

| # | Question | Decision |
|---|----------|----------|
| 1 | Source of model list | Backend proxy with 24 h cache (`ir.config_parameter`) |
| 2 | Price format | `$X.XX in / $X.XX out` per 1M tokens |
| 3 | Custom model UX | Free-typing + autocomplete; custom values saved as-is |
| 4 | List organisation | Grouped by provider (Anthropic, OpenAI, Google, …) |

## Architecture

```
Settings Form (Browser)
       │
       │  mount: GET /solar_ai/openrouter/models
       ▼
SolarAiModelsController
  cache hit  → return ir.config_parameter "solar_ai.models_cache"
  cache miss → fetch openrouter.ai/api/v1/models → normalise → cache → return
       │
       ▼
ModelSelectWidget (OWL)
  input (always editable) + floating dropdown
  grouped by provider, each row: name + "$in / $out"
  custom value → no price shown
```

## Data contract

```json
{
  "models": [
    {
      "id": "anthropic/claude-3.5-haiku",
      "name": "Claude 3.5 Haiku",
      "provider": "Anthropic",
      "pricing_in": 0.80,
      "pricing_out": 4.00
    }
  ],
  "cached": true
}
```

## Files

| File | Action |
|------|--------|
| `controllers/openrouter_models.py` | NEW — proxy + cache |
| `controllers/__init__.py` | import openrouter_models |
| `tests/test_solar_ai_models_endpoint.py` | NEW — 5 TDD tests |
| `static/src/components/model_select_widget.js` | NEW — OWL widget |
| `static/src/components/model_select_widget.xml` | NEW — OWL template |
| `static/src/components/model_select_widget.scss` | NEW — styles |
| `views/res_config_settings_views.xml` | add `widget="solar_ai_model_select"` |
| `__manifest__.py` | register new JS/CSS assets |

## Tests (TDD, Python)

- `test_models_endpoint_returns_normalised_list` — mock HTTP, assert structure
- `test_cache_hit_skips_http` — second call, mock not invoked
- `test_cache_expired_refetches` — ts = now − 90000, mock invoked again
- `test_fallback_returns_stale_cache_on_network_error` — ConnectionError + stale cache present
- `test_fallback_returns_empty_on_no_cache_and_error` — ConnectionError + no cache
- `test_pricing_normalised_to_per_million` — prompt=0.0000008 → pricing_in=0.80
