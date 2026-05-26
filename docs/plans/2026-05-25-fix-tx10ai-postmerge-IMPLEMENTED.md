# Implementation Log: Fix tx10_ai post-merge issues

**Date:** 2026-05-26
**Branch:** `feat/tx10-ai-discuss`
**Task:** `2026-05-25-fix-tx10ai-postmerge`

---

## Goal

Виправити три проблеми після деплою tx10_ai:
1. Бот не відповідає (silent fail при порожньому API ключі)
2. Старий `solar_ai` navbar ще видно
3. Помилки мовчки проглатуються

---

## Files Added

| File | Purpose |
|------|---------|
| `custom_addons/tx10_ai/controllers/bot_info.py` | JSON-RPC endpoint `/tx10_ai/bot_partner` → повертає partner_id бота |
| `custom_addons/tx10_ai/static/src/systray/tx10_ai_systray.js` | OWL systray компонент → відкриває DM з ботом через `mail.store.openChat` |
| `custom_addons/tx10_ai/static/src/systray/tx10_ai_systray.xml` | OWL template для systray кнопки (іконка `fa-comments`) |
| `custom_addons/tx10_ai/i18n/uk.po` | Ukrainian translations для user-facing error messages |

## Files Modified

| File | Change |
|------|--------|
| `custom_addons/tx10_ai/models/tx10_ai_service.py` | Додано `error_code` до всіх error returns у `chat()` та `chat_with_tools()` |
| `custom_addons/tx10_ai/models/tx10_ai_chat.py` | `_ERROR_USER_MESSAGES` dict + `_format_error()` + anti-silence guard + помилка через friendly message |
| `custom_addons/tx10_ai/controllers/__init__.py` | Зареєстровано `bot_info` |
| `custom_addons/tx10_ai/__manifest__.py` | Ім'я `TX10 AI` → `TeamX10 AI`; systray assets в `web.assets_backend` |
| `custom_addons/tx10_ai/__init__.py` | import order (alphabetical) |
| `custom_addons/tx10_ai/models/__init__.py` | import order (alphabetical) |
| `custom_addons/tx10_ai/views/res_config_settings_views.xml` | Block title `TX10 AI Assistant` → `TeamX10 AI Assistant` |
| `custom_addons/tx10_ai/tests/test_tx10_ai_discuss.py` | Додано `TestTx10AiErrorSurfacing` (4 тести) |
| `custom_addons/solar_demo/__manifest__.py` | Removed `solar_ai` from `depends` |
| `docker-compose.yml` | Removed `OPENROUTER_API_KEY` env var (key now via Settings UI) |

## Files Deleted

| File/Dir | Reason |
|----------|--------|
| `custom_addons/solar_ai/` (entire directory) | Module retired; `tx10_ai` is the replacement |

---

## Key Patterns Established

### Error code protocol
`tx10_ai_service.py` returns both `error` (human-readable/exception string) and `error_code` (machine-readable key). Chat layer reads `error_code` to map to localized message.

### Anti-silence guarantee
`_run_agent` always posts something:
```python
if not response_text:
    response_text = self._format_error("unknown")
if self.channel_id:
    self.channel_id.sudo().message_post(...)
```
Previously: `if response_text and self.channel_id:` — bot was silent on empty response.

### Admin-only error codes
`_format_error()` appends `— код: {error_code}` only for `base.group_system` users. Regular users see friendly Ukrainian text only.

### Systray pattern
New OWL component uses `mail.store.openChat({partnerId})` — native Discuss DM, idempotent (opens existing chat if already created). Bot partner_id fetched once via RPC at `onWillStart`.

---

## Manual Steps Required (not automated)

| Step | Command | Pre-condition |
|------|---------|---------------|
| T09 | Uninstall `solar_ai` from isolar DB: `odoo-bin shell -d isolar` → `env['ir.module.module'].search([('name','=','solar_ai')]).button_immediate_uninstall(); env.cr.commit()` | Docker running |
| T09b | Delete orphan config params: `env['ir.config_parameter'].sudo().search([('key', 'like', 'solar_ai.%')]).unlink(); env.cr.commit()` | After T09 |
| T11 | `./docker-restart.sh` — confirm clean startup | After T09, T09b |
| T19 | UI: one robot icon (fa-comments) in navbar, click → floating chat opens, Settings shows "TeamX10 AI Assistant" | After T11 |
| T20 | Bot behavior: empty key → friendly error; real key → answer; bad key → friendly error (no silence) | After T11 |

---

## Deviations from Plan

| # | Plan | Actual | Reason |
|---|------|--------|--------|
| 1 | Font Awesome icon: prefer `fa-robot` (FA5) | Used `fa-comments` (FA4) | Odoo 19 ships FA4.7 — `fa-robot` absent in `font-awesome.css` |
| 2 | `_lt` from `odoo.tools.translate` | `from odoo import _lt` | Odoo 19 pattern (confirmed in `project_stock_account`) |
| 3 | Systray: `useService("rpc")` + `openChat({partnerId})` | Direct `rpc` import + `Thread.getOrFetch` by `channel_id` | (a) `useService("rpc")` absent in Odoo 19 — use `import { rpc } from "@web/core/network/rpc"`. (b) `openChat({partnerId})` fails for bot partner (no linked `res.users`) — use channel_id directly. Endpoint changed from `/tx10_ai/bot_partner` → `/tx10_ai/bot_channel`. |

---

## Verification Evidence

- T18: `grep -r "solar_ai" custom_addons/ --include=*.py --include=*.xml --include=*.js` → zero results ✓
- T21: `gitnexus detect-changes` → risk=LOW, affected_processes=0, 14 symbols changed, all in `tx10_ai` ✓
- Ruff: no new errors introduced in modified files ✓
- Impact analysis: `_do_agent_cycle` risk=LOW (d=1: `_run_agent` only), `_run_agent` risk=LOW (d=1: `_cron_run_pending_chats` only) ✓
- E2E (Playwright, 2026-05-26): systray click opens DM ✓, bot replies `🔌 AI-асистента ще не налаштовано` on empty key ✓, admin sees `— код: no_api_key` ✓, no Solar AI in navbar/settings ✓

---

## Tests Added

`TestTx10AiErrorSurfacing` in `tests/test_tx10_ai_discuss.py`:

| Test | What it verifies |
|------|-----------------|
| `test_no_api_key_bot_replies` | Anti-silence: bot posts when key empty |
| `test_http_error_posts_service_unavailable` | HTTP 500 → friendly "недоступний" message |
| `test_admin_sees_error_code` | Admin (`base.group_system`) sees `— код: no_api_key` |
| `test_non_admin_no_error_code` | Regular user does NOT see error code |

---

## IT-Team Review (2026-05-26) — Fixed

Full 9-persona review of `feat/tx10-ai-discuss → develop`: 3 BLOCKER, 19 MAJOR.
Scope chosen: **Critical + quick wins**. Fixed in this branch:

| # | Finding | Fix |
|---|---------|-----|
| B1 | IDOR — `project_user` had ACL but no record rule → read all users' chats | ir.rule extended to `group_project_user`; `migrations/19.0.1.1.0/post-migration.py` force-updates the noupdate rule on existing installs |
| M6 | `int(action.get('id'))` → TypeError when id absent | `_require_action_id()` helper raises clear `ValueError` |
| M2 | Leftover `solar_ai/` source on disk | Removed (was only stale `__pycache__`) |
| M4 | docker-compose installed `solar_demo` not `tx10_ai` | `-i solar_demo,tx10_ai` |
| M10 | Systray click silent when channel not bootstrapped | Re-fetch on click + warning notification fallback |
| M11-13 | model_select_widget a11y: keyboard nav, group ARIA, loading announce | ArrowUp/Down/Enter/Escape + `aria-activedescendant`; `aria-hidden` header; `role=status aria-live` |
| M14-19 | Untested: olg_generate_placeholder, activity_schedule confirm, get_record_summary/open_model_list tools, ambiguous-confirm fallback, CAS already-processed | Tests added (10 new). `get_record_summary` bug uncovered: registry used `user_id` (invalid on Odoo 19 `project.task`) → fixed to `user_ids` |
| M16 | T-ADM E2E was vacuous (read stale DB) | Rewritten to trigger a fresh error and assert the new reply |

Verification: 63 Python tests pass (0 failed, 0 errors); 10 Playwright E2E pass.

### Deferred to follow-up (not in this branch)

| # | Finding | Why deferred |
|---|---------|--------------|
| B2 | No migration to clean orphan `solar_ai` DB records + copy prod API key to `tx10_ai` key | Production deployment concern; dev DB already cleaned manually. Needs a deploy-time migration + key-copy step before prod rollout |
| B3 | PR too large (103 files, +13.9k LOC) | Branch already built as one unit; splitting now = churn. Process note for future work |
| M1 | Rate limiter in-memory per-worker | Known limitation (TODO in `_guards.py`); needs Redis/PG-backed shared limiter |
| M3 | OpenRouter API key plaintext in `ir.config_parameter` | Documented design decision (`_AT_REST_NOTE`); secret-manager migration is a separate effort |
| M5 | ir_cron fires every 1 min unconditionally | Low impact; add min-interval/jitter guard later |
| M7 | Chat row lock held across 25s LLM HTTP call | Architectural; move HTTP outside the locked transaction (queue/commit-before-call) |
| M8 | Global `discuss.channel._message_post_after_hook` member query on every post | Perf; add cheap pre-filter before the member search |
| M9 | `tx10_ai` manifest hard-depends on `solar_project` vertical | Decouple to make the bot reusable outside the solar deployment |
