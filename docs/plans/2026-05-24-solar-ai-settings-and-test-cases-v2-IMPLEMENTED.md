# Solar AI Settings UI + Test-Cases Docs v2 — Implementation Log

**Plan:** `2026-05-24-solar-ai-settings-and-test-cases-v2.md`
**Date:** 2026-05-24
**Branch:** `feat/solar-ai-settings`

---

## Goal

Add a `res.config.settings` Settings UI for the OpenRouter API key + default model, extend
test coverage (service read-path, empty-credential edge cases), reconcile the
`config_params.xml` seed with the new UI, and save the manual test-case catalogue to
`docs/testing/`.

---

## Routes / Files Added & Modified

```
custom_addons/solar_ai/
  models/
    res_config_settings.py        NEW — solar_ai_openrouter_api_key + solar_ai_default_model
                                        (config_parameter= binding to ir.config_parameter)
    __init__.py                   MOD — import res_config_settings
    solar_ai_service.py           MOD — extracted _resolve_model(); blank default_model
                                        now falls back to hardcoded default

  data/
    config_params.xml             MOD — removed empty openrouter_api_key seed; added
                                        noupdate/reinstall behaviour comment

  controllers/
    _guards.py                    MOD — expanded check_rate_limit docstring (per-worker
                                        limitation + future-fix TODO)

  views/
    res_config_settings_views.xml NEW — Settings form block "Solar AI Assistant" under
                                        //app[@name='project'] (password-masked key field)

  __manifest__.py                 MOD — registered views/res_config_settings_views.xml

  tests/
    test_solar_ai_settings.py     NEW — 11 tests (TestSolarAiConfigSettings) +
                                        1 test (TestSolarAiSettingsView, xpath guard)
    __init__.py                   MOD — import test_solar_ai_settings

docs/testing/
  solar-ai-chat-test-cases.md     NEW — L0-L4 manual test-case catalogue + code map for E2E
```

---

## Key Patterns Established

| Pattern | Location | Why |
|---------|----------|-----|
| `config_parameter=` field binding | `res_config_settings.py` | Char field auto-syncs to `ir.config_parameter` — no manual get/set |
| `_AT_REST_NOTE` constant in help text | `res_config_settings.py` | Surfaces plaintext-at-rest warning at the field level |
| `widget="password"` on key field | `res_config_settings_views.xml` | Masks API key in the Settings form |
| xpath silent-fail guard test | `test_solar_ai_settings.py:TestSolarAiSettingsView` | `get_views()` arch assertion catches a broken `//app[@name='project']` xpath |
| `_resolve_model()` helper | `solar_ai_service.py` | DRY model resolution; blank `default_model` falls back instead of sending `model=''` |
| Seed = source of truth split | `config_params.xml` | API key set only via Settings UI; `default_model` seeded with reinstall-behaviour comment |

---

## Deviations from Plan (+ reasons)

| Deviation | Reason |
|-----------|--------|
| Added 5 tests beyond the planned 7 (12 total in file) | IT-team review (2 gates) flagged untested negative paths: empty-credential `chat()`/`chat_with_tools()` end-to-end, `classify_document_text` no-key degradation, empty-string `default_model` fallback |
| Extracted `_resolve_model()` in `solar_ai_service.py` (not in original plan) | Review MAJOR #3: `ir.config_parameter` keeps `''` (does not delete), so the `get_param` default never fired for a blank model — guard prevents sending `model=''` to OpenRouter |
| Expanded `_guards.py` docstring; fixed RUF002 (`×`→`*`) | Plan text used a unicode multiplication sign that ruff rejects |
| Doc is 139 lines (plan estimated 150+) | More compact markdown; all L0-L4 tables + code map present |

---

## Verification Evidence

| Check | Result |
|-------|--------|
| `TestSolarAiConfigSettings` | 11 tests pass |
| `TestSolarAiSettingsView` (xpath guard) | 1 test passes |
| Full module regression | 59 tests pass (47 pre-existing + 12 new) |
| Lint (`ruff check custom_addons/solar_ai`) | 0 errors |
| Manual UI (Playwright) | Settings → Project → "Solar AI Assistant" block renders; key masked; save → reload persists value |
| GitNexus `detect_changes` | risk LOW, 0 affected processes |

---

## IT-Team Review Findings Addressed

**Gate 1 (Tasks 0-2):** 1 MAJOR (test coverage) → added 3 empty-credential degradation tests.

**Gate 2 (full branch):** 4 MAJOR:
- #1 per-worker rate limit — accepted as documented out-of-scope limitation (shared-state fix is a separate infra task).
- #2 `classify_document_text` no-key path — added graceful-degradation test.
- #3 empty `default_model` — added `_resolve_model()` guard + isolated test.
- #4 no-key chat test clarity — renamed/clarified docstring (tests the guard short-circuit, not live HTTP).

---

## Commits

```
959eb38 [ADD] solar_ai: res.config.settings fields for OpenRouter key + model (TDD, 6 tests)
ff82357 [IMP] solar_ai: remove duplicate api_key seed; document per-worker rate-limit (#1 #3)
6544f89 [ADD] solar_ai: empty-credential degradation tests for chat/chat_with_tools + default_model fallback
80d43f7 [ADD] solar_ai: Settings UI block for OpenRouter API key and default model (xpath guard test)
c0e8c9a [ADD] docs: solar AI chat manual test cases L0-L4 + code map for E2E (v2)
4b18872 [IMP] solar_ai: blank default_model falls back to hardcoded default + negative-path tests
```

**PR:** _(to be filled after creation)_
