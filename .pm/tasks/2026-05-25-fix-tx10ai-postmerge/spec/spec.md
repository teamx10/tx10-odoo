# Spec: Fix tx10_ai post-merge issues

> Task: `2026-05-25-fix-tx10ai-postmerge`
> Branch: `feat/tx10-ai-discuss` (PR #3 → `develop`)
> Module: `custom_addons/tx10_ai/`
> Date: 2026-05-25

---

## Problem Statement

Three regressions surfaced after PR #3 deployed the `tx10_ai` Discuss-bot module:

1. **Bot appears but never replies.** "TeamX10 AI" sends a welcome message but all subsequent user messages receive no response. Root cause: `docker-compose` passes `OPENROUTER_API_KEY` env but nothing maps it into `ir.config_parameter`; `tx10_ai_service.py` reads only from `ir.config_parameter`; the key is always empty; `chat_with_tools` returns `{error:"no_api_key", content:""}` which is falsy; the guard at `tx10_ai_chat.py:109` (`if response_text and self.channel_id`) skips the `message_post` call entirely — the bot silently does nothing.

2. **Old "Solar AI" navbar button still shows.** The `fa fa-android` robot icon in the systray still opens the legacy "Solar AI" panel. `solar_ai` remains installed because `docker-compose` starts with `-i solar_demo` and `solar_demo.__manifest__` depends on `solar_ai`.

3. **All errors are silent.** Every error exit path in `tx10_ai_service.py` (`chat`, `chat_with_tools`) returns `content:""`. The anti-silence guard at `tx10_ai_chat.py:109` then also suppresses these empty strings. Users see nothing; only server logs contain the error. The `_cron_run_pending_chats` exception handler also swallows errors to log-only.

---

## Acceptance Criteria

### AC-1: Bot replies (Problem 1)

**Given** the `tx10_ai.openrouter_api_key` system parameter is set to a valid key via Settings UI  
**When** a user sends a message in a Discuss channel that has the TeamX10 AI bot as a member  
**Then** within 60 seconds the bot posts a non-empty reply in that same channel

**Given** the `tx10_ai.openrouter_api_key` system parameter is empty or absent  
**When** a user sends a message in a channel with the bot  
**Then** within 60 seconds the bot posts a visible friendly error message (not silence)

**Given** the `OPENROUTER_API_KEY` environment variable is set in `docker-compose.yml`  
**Then** that variable is absent from the `odoo` service `environment:` block — API key is managed exclusively through Settings UI (`/odoo/settings` → "TeamX10 AI Assistant" block)

**Given** a test environment with `tx10_ai.openrouter_api_key` not set  
**When** `_cron_run_pending_chats()` runs  
**Then** `mail.message` records exist on the channel authored by `partner_ai_bot` after the cron run (verifiable in `test_tx10_ai_discuss.py::TestTx10AiErrorSurfacing`)

### AC-2: Solar AI removed (Problem 2)

**Given** the production Odoo instance  
**When** the navbar is rendered  
**Then** exactly one AI-related systray entry is shown — the `tx10_ai` button with a standard icon (not `fa-android`) and `title="TeamX10 AI"`

**Given** the navbar systray `tx10_ai` button is clicked  
**Then** the native Discuss floating chat window opens for the TeamX10 AI bot partner (via `mail.store.openChat({partnerId})`) — not the old "Solar AI" side panel

**Given** the `solar_ai` module has been uninstalled  
**When** running `grep -ri "solar_ai\|solar\.ai\." custom_addons/ --include="*.py" --include="*.xml" --include="*.js"`  
**Then** the command returns zero matches (excluding `solar_project` references, which remain)

**Given** the Settings page at `/odoo/settings`  
**Then** exactly one AI settings block is shown, titled "TeamX10 AI Assistant" — no "Solar AI Assistant" block exists

**Given** `custom_addons/solar_demo/__manifest__.py`  
**Then** its `depends` list does not contain `solar_ai`

**Given** the git repository  
**Then** `custom_addons/solar_ai/` directory does not exist (removed via `git rm -r`)

### AC-3: Error surfacing (Problem 3)

**Given** the bot receives a request and `tx10_ai.openrouter_api_key` is unset  
**When** `_do_agent_cycle` runs  
**Then** it returns a non-empty Markup string containing the localized text for `no_api_key` (e.g. "не налаштовано" in Ukrainian) — it does NOT return `Markup("")`

**Given** OpenRouter returns HTTP 5xx  
**When** `_do_agent_cycle` runs  
**Then** it returns a non-empty Markup string containing the localized text for `http_error` (e.g. "тимчасово недоступний")

**Given** `_do_agent_cycle` raises an unhandled exception  
**When** `_run_agent` catches it  
**Then** `response_text` is set to a friendly fallback string — not an empty string — and `message_post` is called on the channel

**Given** the guard in `_run_agent` (previously `if response_text and self.channel_id`)  
**Then** the guard is changed so `message_post` is called whenever `self.channel_id` exists, regardless of whether `response_text` is truthy — `response_text` is guaranteed non-empty by the step above

**Given** a user in `base.group_system` is the chat owner  
**When** any error occurs (e.g. `no_api_key`)  
**Then** the bot message body contains the suffix `— код: no_api_key` (machine-readable code appended after the friendly text)

**Given** a user NOT in `base.group_system` is the chat owner  
**When** the same `no_api_key` error occurs  
**Then** the bot message body does NOT contain `— код:` — only the friendly localized text is shown

**Given** `_ERROR_USER_MESSAGES` dict exists at module level in `tx10_ai_chat.py`  
**Then** it covers at minimum these keys: `no_api_key`, `http_error`, `network_error`, `empty_choices`, `terminated_content_filter`, `terminated_length`, `unknown`

**Given** all error message strings in `tx10_ai_chat.py`  
**Then** they are wrapped with Odoo `_()` or `_lt()` i18n functions and have corresponding entries in `tx10_ai/i18n/uk.po`

---

## Out of Scope

- Reworking the `ir.cron` async architecture. The ≤60s reply latency (cron-triggered via `_trigger()`) is by design; no change to the scheduling mechanism.
- `olg_proxy` error UX — the JSON-API path has a separate error surface; not the reported regression.
- Changing model names (`tx10.ai.*`), the technical module id `tx10_ai`, or database table names.
- Adding real-time WebSocket push for bot replies (would require significant OWL/bus work outside this scope).
- Multi-language `.po` files beyond Ukrainian (`uk.po`). Russian and other locales may be added in a follow-up.
- Modifying `solar_project` in any way — it remains installed and `tx10_ai` continues to depend on it.
- Changing the `ir.cron` `_cron_run_pending_chats` exception handler to re-raise (log-only on the outer cron loop is acceptable; the inner `_run_agent` now surfaces errors to users, which is the fix).

---

## Definition of Done

### Code

- [ ] `custom_addons/tx10_ai/models/tx10_ai_service.py` — every error return dict includes a stable `error_code` field (`no_api_key`, `http_error`, `network_error`, `empty_choices`, `terminated_content_filter`, `terminated_length`)
- [ ] `custom_addons/tx10_ai/models/tx10_ai_chat.py` — module-level `_ERROR_USER_MESSAGES` dict present; `_format_error()` helper implemented; `_do_agent_cycle` returns friendly Markup on error (never `Markup("")`); `_run_agent` guard at line ~109 always calls `message_post` when `self.channel_id` exists
- [ ] `custom_addons/tx10_ai/models/tx10_ai_chat.py` — `_format_error()` appends `— код: {code}` suffix only for users in `base.group_system`
- [ ] `custom_addons/tx10_ai/i18n/uk.po` — entries for all `_ERROR_USER_MESSAGES` strings
- [ ] `custom_addons/solar_demo/__manifest__.py` — `solar_ai` removed from `depends`
- [ ] `custom_addons/solar_ai/` — directory deleted from git (`git rm -r`)
- [ ] `custom_addons/tx10_ai/controllers/bot_info.py` — new JSON route `/tx10_ai/bot_partner` returning `partner_id` (and `channel_id` as fallback)
- [ ] `custom_addons/tx10_ai/static/src/systray/tx10_ai_systray.js` — systray component registered, uses `mail.store.openChat({partnerId})`
- [ ] `custom_addons/tx10_ai/static/src/systray/tx10_ai_systray.xml` — icon is NOT `fa-android`; `title`/`aria-label` = "TeamX10 AI"
- [ ] `custom_addons/tx10_ai/__manifest__.py` — systray JS/XML/SCSS registered in `web.assets_backend`; `name` field updated to `"TeamX10 AI"`
- [ ] `custom_addons/tx10_ai/views/res_config_settings_views.xml` — block title is `"TeamX10 AI Assistant"` (not "TX10 AI Assistant")
- [ ] `docker-compose.yml` (or equivalent) — `OPENROUTER_API_KEY` env var removed from `odoo` service

### Tests

- [ ] `custom_addons/tx10_ai/tests/test_tx10_ai_discuss.py` — `TestTx10AiErrorSurfacing` class added with:
  - `test_no_api_key_posts_friendly_message` — mocks `httpx.post` not called; asserts a bot `mail.message` exists on channel after cron run; body contains "не налаштовано" (or translation key equivalent)
  - `test_http_error_posts_friendly_message` — mocks `httpx.post` to raise `HTTPStatusError`; asserts bot posts "тимчасово недоступний"
  - `test_admin_sees_error_code` — chat owner is `base.group_system` user; asserts posted body contains `код: no_api_key`
  - `test_non_admin_no_error_code` — chat owner is a regular user; asserts posted body does NOT contain `— код:`
- [ ] All existing tests in `tx10_ai` still pass: `test_tx10_ai.py`, `test_tx10_ai_settings.py`, `test_tx10_ai_models_endpoint.py`, `test_tx10_ai_agent.py`
- [ ] Run command: `./odoo-bin -d <db> --test-tags tx10_ai --stop-after-init` exits 0

### Manual Verification

- [ ] Navigate to `/odoo/settings` — one settings block titled "TeamX10 AI Assistant" visible; no "Solar AI Assistant" block
- [ ] Set a valid OpenRouter API key in Settings → send message in bot channel → bot replies within 60s
- [ ] Clear the API key → send message → bot replies with friendly "не налаштовано" error (admin account also sees `— код: no_api_key`)
- [ ] Navbar shows exactly one AI systray icon; icon is NOT `fa-android`; clicking opens the Discuss floating chat for TeamX10 AI
- [ ] `grep -ri "solar_ai\|solar\.ai\." custom_addons/ --include="*.py" --include="*.xml" --include="*.js"` returns zero matches
- [ ] `gitnexus detect-changes` output lists only `tx10_ai` (and `solar_demo` manifest) as affected symbols — no unexpected blast radius
