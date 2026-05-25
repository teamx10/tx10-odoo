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

---

## Verification Evidence

- T18: `grep -r "solar_ai" custom_addons/ --include=*.py --include=*.xml --include=*.js` → zero results ✓
- T21: `gitnexus detect-changes` → risk=LOW, affected_processes=0, 14 symbols changed, all in `tx10_ai` ✓
- Ruff: no new errors introduced in modified files ✓
- Impact analysis: `_do_agent_cycle` risk=LOW (d=1: `_run_agent` only), `_run_agent` risk=LOW (d=1: `_cron_run_pending_chats` only) ✓

---

## Tests Added

`TestTx10AiErrorSurfacing` in `tests/test_tx10_ai_discuss.py`:

| Test | What it verifies |
|------|-----------------|
| `test_no_api_key_bot_replies` | Anti-silence: bot posts when key empty |
| `test_http_error_posts_service_unavailable` | HTTP 500 → friendly "недоступний" message |
| `test_admin_sees_error_code` | Admin (`base.group_system`) sees `— код: no_api_key` |
| `test_non_admin_no_error_code` | Regular user does NOT see error code |
