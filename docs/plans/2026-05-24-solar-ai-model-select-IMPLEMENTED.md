# Solar AI — Model Select Widget (IMPLEMENTED)

**Date**: 2026-05-24
**Plan**: `2026-05-24-solar-ai-model-select.md`
**Branch**: feat/solar-ai-model-select (to be created)

## What was done

Replaced the free-text `Default Model` field in Settings → Solar AI Assistant with
a searchable combobox backed by a live OpenRouter models endpoint.

## Files added

| File | Purpose |
|------|---------|
| `controllers/openrouter_models.py` | Backend proxy: fetches openrouter.ai/api/v1/models, caches 24 h in ir.config_parameter |
| `tests/test_solar_ai_models_endpoint.py` | 6 TDD tests (normalisation, cache hit, cache expiry, 2× fallback, pricing) |
| `static/src/components/model_select_widget.js` | OWL widget — combobox with autocomplete |
| `static/src/components/model_select_widget.xml` | OWL template — grouped dropdown + price hint |
| `static/src/components/model_select_widget.scss` | Styles — grid layout name/id/price per row |

## Files modified

| File | Change |
|------|--------|
| `controllers/__init__.py` | +`openrouter_models` import |
| `tests/__init__.py` | +`test_solar_ai_models_endpoint` import |
| `views/res_config_settings_views.xml` | `widget="solar_ai_model_select"` on `solar_ai_default_model` |
| `__manifest__.py` | Registered 3 new assets in `web.assets_backend` |

## Key patterns

- **Cache**: `ir.config_parameter` stores JSON + unix timestamp. TTL 24 h checked in Python.
- **Fallback**: network error → return stale cache if available, else `[]`.
- **OWL widget**: registered via `registry.category("fields").add(...)`, saves via `props.record.update(...)`.
- **Pricing**: `float(pricing.prompt) * 1_000_000` → per-1M USD, shown as `$X.XX in / $X.XX out`.
- **Custom model**: free-typing always enabled; unknown IDs saved as-is without price hint.

## Deviations from plan

None.

## Verification

- `ruff check` — CLEAN on all new/modified Python files
- Python tests: 6 tests in `TestSolarAiModelsEndpoint` — require Odoo test runner
  ```bash
  ./odoo-bin -d <db> --test-tags :TestSolarAiModelsEndpoint --stop-after-init -u solar_ai
  ```
- OWL widget: requires browser test (install module, open Settings → Solar AI Assistant)

## Next step

Open PR: `feat/solar-ai-model-select` → `19.0`
