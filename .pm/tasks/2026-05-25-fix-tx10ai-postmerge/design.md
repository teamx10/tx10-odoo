# Fix tx10_ai post-merge issues — design & implementation plan

> Branch: `feat/tx10-ai-discuss` (PR #3 → `develop`). This file is both the tx2 design
> artifact and the implementation plan. All work continues on the existing feature branch.

## Context

PR #3 migrated the AI assistant from `solar_ai` into a new Discuss-bot module `tx10_ai`.
After deploy, three problems surfaced (see `[Image #1]`):

1. **"TeamX10 AI" appears but never replies.** The welcome message shows, but user
   messages get no answer.
2. **The navbar robot still opens the old "Solar AI" panel**, with an off-brand
   `fa-android` icon. The old module was never removed.
3. **Failures are silent.** Missing API key / network / content-filter errors produce no
   user-visible message at all.

### Confirmed root causes (read from disk, not the plan doc)

| # | Root cause | Evidence |
|---|------------|----------|
| 1 | OpenRouter key is empty → `chat_with_tools` returns `{error:"no_api_key", content:""}` → `_do_agent_cycle` returns `Markup.escape("")` = `""` → `_run_agent` line `if response_text...` is falsy → `message_post` skipped. `docker-compose` passes `OPENROUTER_API_KEY` env but **nothing maps it to `ir.config_parameter`**. | `tx10_ai_service.py:126-134`, `tx10_ai_chat.py:189`, `tx10_ai_chat.py:109`, `docker-compose.yml` |
| 2 | `solar_ai` is still installed: `docker-compose` runs `-i solar_demo`, and `solar_demo` depends on `solar_ai`. Its systray (`sequence:5`, icon `fa fa-lg fa-android`) keeps loading. | `solar_demo/__manifest__.py:7`, `solar_ai/.../ai_assistant_systray.xml:13`, `...systray.js:54` |
| 3 | Every service error path returns `content:""` → swallowed at `tx10_ai_chat.py:109`. Cron also swallows exceptions to log only. | `tx10_ai_service.py:80,83,99-104,157-187`; `tx10_ai_chat.py:69-70` |

## Locked decisions (from human review)

| Question | Decision |
|----------|----------|
| Navbar robot fate | **New tx10_ai systray button → opens the TeamX10 AI DM as a floating chat window** (native `mail.store.openChat`). Normal icon (not `fa-android`). |
| API key source | **UI Settings only.** Remove the unused `OPENROUTER_API_KEY` env from `docker-compose`. Settings block must be its own block named **"TeamX10 AI Assistant"** (currently "TX10 AI Assistant"). |
| Error verbosity | **Friendly localized message + a short technical code for project-manager/admin** (e.g. `— код: no_api_key`). |

---

## Part A — Make the bot reply + never fail silently (problems 1 & 3)

These share one fix: route every error through a friendly message and **guarantee the bot
always posts something**.

### A1. `models/tx10_ai_service.py` — add a stable `error_code`
Each error return currently has a free-text `error`. Add a machine-readable `error_code`
to both `chat` and `chat_with_tools` so the chat layer doesn't string-sniff:

- no key → `error_code="no_api_key"`
- `httpx.HTTPStatusError` → `error_code="http_error"` (keep status in `error`)
- `httpx.RequestError` → `error_code="network_error"`
- empty choices → `error_code="empty_choices"`
- `finish_reason in (length, content_filter)` → `error_code=f"terminated_{finish_reason}"`

### A2. `models/tx10_ai_chat.py` — friendly error mapping + anti-silence guarantee
- Add module-level `_ERROR_USER_MESSAGES` dict mapping `error_code` → localized text, e.g.
  `no_api_key → "🔌 AI-асистента ще не налаштовано. Зверніться до адміністратора..."`,
  `network_error/http_error → "⚠️ Сервіс AI тимчасово недоступний. Спробуйте пізніше."`,
  `empty_choices/terminated_content_filter → "🤔 Не вдалося згенерувати відповідь..."`,
  `terminated_length → "✂️ Відповідь завелика, звузьте запит."`, plus `unknown` fallback.
- Add helper `_format_error(self, error_code, exc_name=None)`: returns the friendly text and,
  **if `self.user_id` is in `project.group_project_manager` or `base.group_system`**, appends
  `\n\n— код: {error_code}`.
- In `_do_agent_cycle`: when `llm_result.get("error")`, `return self._format_error(llm_result.get("error_code") or "unknown")` **instead of** `Markup.escape("")`.
- In `_run_agent` (the `except Exception` block): set `response_text = self._format_error("unknown", exc_name=type(exc).__name__)`.
- In `_run_agent`, replace the guard at line 109 so the bot is **never** silent:
  ```python
  if not response_text:
      response_text = self._format_error("unknown")
  if self.channel_id:
      self.channel_id.sudo().message_post(...)
  ```
  (i.e. drop `response_text` from the truthiness gate; always post.)

> Per repo rule: run `gitnexus_impact({target:"_do_agent_cycle"})` and `_run_agent` before
> editing. Both are new, module-internal, called only by the cron → expected risk LOW.

### A3. Tests — `tests/test_tx10_ai_discuss.py`
Add a class `TestTx10AiErrorSurfacing` (mock `httpx.post`):
- **no API key** (param unset) → after `_cron_run_pending_chats`, the channel gets a bot
  message containing the friendly "не налаштовано" text (assert a NEW bot `mail.message`
  exists — proves no silent death).
- **HTTP 500** (`mock_post` raises `HTTPStatusError`) → bot posts the "тимчасово недоступний" text.
- **admin sees code**: with a `group_system` user, the posted body contains `код: no_api_key`;
  with a plain (non-manager) author it does not. (Note: bot users are project managers, so
  pick the group boundary you actually gate on.)

---

## Part B — Remove solar_ai, add a proper systray robot, fix branding (problem 2)

### B1. Drop the dependency, then uninstall, then delete (ORDER MATTERS)
Deleting files while the module is still installed in the DB makes Odoo fail on boot, so:

1. Edit `custom_addons/solar_demo/__manifest__.py`: `depends` `["solar_project","solar_ai"]` → `["solar_project"]`.
   First `grep -ri "solar.ai\|solar_ai" custom_addons/solar_demo/demo/` to confirm the demo
   XML doesn't reference AI models (expected: branding/project data only).
2. **Uninstall `solar_ai` from the running DB** (purges models, systray registry, config
   params, the "Solar AI Assistant" settings block):
   `./odoo-bin shell -d isolar` → `env['ir.module.module'].search([('name','=','solar_ai')]).button_immediate_uninstall(); env.cr.commit()`
   (⚠️ destructive for solar_ai data — that data belongs to the module being retired, so OK.)
3. `git rm -r custom_addons/solar_ai/`.
4. Restart: `./docker-restart.sh` (re-runs `-i tx10_ai`); also `-u solar_demo`.

> `solar_project` stays — `tx10_ai` depends on it.
> Alternative (if shell-uninstall is impractical): drop the DB volume and re-seed clean
> (`docker compose down -v` → boot). Loses demo data; acceptable only if nothing important
> was entered.

### B2. New tx10_ai systray button → floating chat window
- `controllers/bot_info.py` — new `@http.route("/tx10_ai/bot_partner", type="json", auth="user")`
  returning `{"partner_id": <id of tx10_ai.partner_ai_bot>}` (and `channel_id` as fallback).
  Tiny, decoupled — avoids touching the central `ir.http.session_info`.
- `static/src/systray/tx10_ai_systray.js` — register in `registry.category("systray")`.
  `setup()`: `this.store = useService("mail.store")`; fetch the bot partner id once via
  `onWillStart` (`rpc("/tx10_ai/bot_partner")`). `onClick`: `this.store.openChat({ partnerId })`
  (idempotent with bootstrap's `_get_or_create_chat` → same channel, link preserved).
- `static/src/systray/tx10_ai_systray.xml` — button with a **normal** icon. Verify the bundled
  Font Awesome version during impl: prefer `fa fa-robot` (FA5+); if only FA4.7 is shipped, use
  `fa fa-comments` / `fa fa-comment-dots`. `title`/`aria-label`: "TeamX10 AI".
- Register all three (js/xml + any scss) in `__manifest__.py` `web.assets_backend`.

### B3. Branding fixes
- `views/res_config_settings_views.xml:9` — `<block title="TX10 AI Assistant"` → `"TeamX10 AI Assistant"`.
- `__manifest__.py:2` — `"name": "TX10 AI"` → `"TeamX10 AI"` (user-facing). Technical id
  `tx10_ai` and model names `tx10.ai.*` stay unchanged.

### B4. docker-compose hygiene
- Remove the `OPENROUTER_API_KEY: ${OPENROUTER_API_KEY:-}` line from the `odoo` service
  `environment:` and update the adjacent comment (key is configured in Settings UI now).

---

## Reuse / reference

| Need | Source |
|------|--------|
| Floating chat window | `store.openChat({partnerId})` — `addons/mail/static/src/core/common/store_service.js:777` |
| Systray registration pattern | `solar_ai/.../ai_assistant_systray.js:54` (mirror structure, new icon + openChat) |
| `useService("mail.store")` | `addons/mail/static/src/core/web/open_chat_hook.js` |
| Settings block xpath | `tx10_ai/views/res_config_settings_views.xml` (already correct location) |

## Verification (end-to-end)

1. `grep -ri "solar_ai\|solar\.ai\." custom_addons/ --include=*.py --include=*.xml --include=*.js`
   → only `solar_project` references remain; zero `solar_ai`.
2. `./odoo-bin -d <db> --test-tags tx10_ai --stop-after-init` → OK (new error-surfacing tests pass).
3. Boot the app: navbar shows **one** robot (normal icon); click → **floating chat window**
   for TeamX10 AI opens; the old "Solar AI" panel is gone; Settings shows **one** block
   "TeamX10 AI Assistant" (no "Solar AI Assistant").
4. With **empty** key: message the bot → within ≤1 min it replies with the friendly
   "не налаштовано" message (+ code for admin). No silence.
5. Set a real key in Settings → message the bot → it answers normally with clickable links.
6. Kill network / use a bad key → bot replies "тимчасово недоступний". No silence.
7. `gitnexus detect-changes` → only `tx10_ai` (+ `solar_demo` manifest) symbols affected.

## Out of scope
- Reworking the async `ir.cron` architecture (≤60s reply latency is by design; `_trigger()`
  fires it ASAP when cron workers run, which they do in default threaded mode).
- `olg_proxy` html_editor error UX (separate JSON path; not the reported bug).
