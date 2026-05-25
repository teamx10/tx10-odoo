# Architecture: Fix tx10_ai post-merge issues

Date: 2026-05-25
Module: `custom_addons/tx10_ai`
Odoo: 19.0

---

## Component Overview

```
custom_addons/
  tx10_ai/
    __manifest__.py                     MODIFY  name, assets, deps
    models/
      tx10_ai_service.py                MODIFY  add error_code to all error returns
      tx10_ai_chat.py                   MODIFY  _ERROR_USER_MESSAGES, _format_error(), _run_agent anti-silence
    controllers/
      __init__.py                       MODIFY  add bot_info import
      _guards.py                        no change
      bot_info.py                       ADD     /tx10_ai/bot_partner JSON endpoint
    static/src/
      systray/
        tx10_ai_systray.js              ADD     OWL systray component
        tx10_ai_systray.xml             ADD     OWL template
    views/
      res_config_settings_views.xml     MODIFY  label "TeamX10 AI Assistant"

  solar_demo/
    __manifest__.py                     MODIFY  remove "solar_ai" from depends

  solar_ai/                             REMOVE  entire directory (git rm -r)

docker-compose.yml (or .env)           MODIFY  remove OPENROUTER_API_KEY env var
```

Interaction matrix:

```
+------------------+        chat()        +-------------------+
|  tx10_ai_chat.py |--------------------->| tx10_ai_service.py|
|  Tx10AiChat      |<-- error_code -----  | Tx10AiService     |
|  _run_agent()    |                      | chat_with_tools() |
|  _format_error() |                      | chat()            |
+------------------+                      +-------------------+
        |
        | message_post (always guaranteed)
        v
+------------------+
| discuss.channel  |
+------------------+

Browser (systray)
+------------------+        RPC           +-------------------+
| tx10_ai_systray  |--------------------->| bot_info.py       |
| .js (OWL)        |<-- {partner_id} ---  | /tx10_ai/         |
| onClick          |                      |  bot_partner      |
+------------------+                      +-------------------+
        |
        | mail.store.openChat({partnerId})
        v
+------------------+
| Discuss chat     |
+------------------+
```

---

## Part A: Error Surfacing Architecture

### Error Code Contract

| error_code              | Trigger condition                              | User message key (i18n)                              | Visible to non-admin? |
|-------------------------|------------------------------------------------|------------------------------------------------------|-----------------------|
| `no_api_key`            | `_build_headers()` returns None                | `_("AI is not configured. Contact your administrator.")` | yes (no code shown)   |
| `http_error`            | `httpx.HTTPStatusError` raised                 | `_("AI service returned an error. Try again later.")`    | yes                   |
| `network_error`         | `httpx.RequestError` raised                    | `_("Could not reach AI service. Check your connection.")` | yes                  |
| `empty_choices`         | `choices` list is empty in response JSON       | `_("AI returned an empty response.")`                | yes                   |
| `terminated_length`     | `finish_reason == "length"`                    | `_("AI response was cut off (token limit reached).")` | yes                  |
| `terminated_content_filter` | `finish_reason == "content_filter"`       | `_("AI response was blocked by content filter.")`    | yes                   |

Code suffix rule: `_format_error()` appends ` [error_code]` only when
`self.env.user.has_group("base.group_system")` is True.

### _format_error() Design

```
Input
  error_code: str       — one of the six codes above
  env: Environment      — current Odoo env (for group check)

Logic
  1. Look up human_msg = _ERROR_USER_MESSAGES.get(error_code)
     If missing → fallback: _("An unexpected AI error occurred.")

  2. If env.user.has_group("base.group_system"):
       suffix = Markup(" <small>[%s]</small>") % error_code
     Else:
       suffix = Markup("")

  3. Return Markup.escape(human_msg) + suffix

Output
  Markup — safe for message_post(body=...)
```

`_ERROR_USER_MESSAGES` is a module-level dict in `tx10_ai_chat.py`, values are
`_lt(...)` lazy strings so they are translated at call time:

```python
from odoo import _lt
_ERROR_USER_MESSAGES = {
    "no_api_key":                _lt("AI is not configured. Contact your administrator."),
    "http_error":                _lt("AI service returned an error. Try again later."),
    "network_error":             _lt("Could not reach AI service. Check your connection."),
    "empty_choices":             _lt("AI returned an empty response."),
    "terminated_length":         _lt("AI response was cut off (token limit reached)."),
    "terminated_content_filter": _lt("AI response was blocked by content filter."),
}
```

### Anti-silence Guarantee

Current `_run_agent` silently drops the message when `response_text` is falsy
(condition: `if response_text and self.channel_id`). Fix:

```
Before (problematic):
  response_text = self._do_agent_cycle()
  if response_text and self.channel_id:        # ← silent drop on error
      self.channel_id.message_post(...)

After (guaranteed post):
  response_text = self._do_agent_cycle()
  if not response_text:
      # _do_agent_cycle returned empty — surface the last known error or a generic fallback
      error_code = getattr(self, '_last_error_code', 'unknown')
      response_text = self._format_error(error_code)
  if self.channel_id:                          # ← post unconditionally if channel exists
      self.channel_id.message_post(body=response_text, ...)
```

Additionally, `_do_agent_cycle` must propagate `error_code` from `llm_result`
to `_format_error()` instead of returning empty string:

```
Old path (in _do_agent_cycle):
  if llm_result.get("error") ...:
      return Markup.escape(llm_result.get("content") or "")  # ← "" if content empty

New path:
  if llm_result.get("error"):
      return self._format_error(llm_result["error"])         # ← always returns Markup text
```

---

## Part B: Solar AI Removal + New Systray

### Removal Sequence (ORDER MATTERS)

```
Step 1  Edit solar_demo/__manifest__.py
        Remove "solar_ai" from depends list.
        Rationale: must happen first so Odoo dependency resolver does not
        re-install solar_ai when solar_demo is updated.

Step 2  Shell-uninstall solar_ai from the running database
        $ ./odoo-bin shell -d <db>
        >>> env['ir.module.module'].search([('name','=','solar_ai')]).button_uninstall()
        >>> env.cr.commit()
        Rationale: Odoo tracks installed modules in ir.module.module.
        Removing files without uninstalling leaves a broken DB entry.

Step 3  git rm -r custom_addons/solar_ai/
        Rationale: after DB uninstall the filesystem can safely be cleared.
        Reverse order would cause import errors on next server start.

Step 4  Update tx10_ai/__manifest__.py
        Rename module: "TX10 AI" → "TeamX10 AI"
        (solar_ai was never in tx10_ai depends — no depends change needed here)

Step 5  Update views/res_config_settings_views.xml
        Change settings block string to "TeamX10 AI Assistant"

Step 6  Remove OPENROUTER_API_KEY from docker-compose environment block
        Rationale: key now lives exclusively in ir.config_parameter
        (tx10_ai.openrouter_api_key); env-var passthrough is unused and a
        credential-exposure risk.
```

### New Systray Component

File: `custom_addons/tx10_ai/static/src/systray/tx10_ai_systray.js`
Template: `custom_addons/tx10_ai/static/src/systray/tx10_ai_systray.xml`

```
Component: Tx10AiSystray (OWL Component)
  State
    partnerId: number | null = null

  Lifecycle
    onWillStart()
      → await rpc("/tx10_ai/bot_partner", {})
      → this.partnerId = result.partner_id   (null on failure — button hidden)

  Template (tx10_ai_systray.xml)
    <t t-name="tx10_ai.Systray">
      <li t-if="partnerId" class="o_menu_systray_item">
        <button t-on-click="onClick">AI</button>
      </li>
    </t>

  onClick()
    → useChatWindow() service or mail.store.openChat({ partnerId: this.partnerId })
    → opens Discuss DM with the bot partner

Registry registration (bottom of .js):
  registry.category("systray").add("tx10_ai.Systray", Tx10AiSystray, { sequence: 5 })
```

Asset registration in `__manifest__.py` assets block:
```python
"web.assets_backend": [
    ...existing...
    "tx10_ai/static/src/systray/tx10_ai_systray.js",
    "tx10_ai/static/src/systray/tx10_ai_systray.xml",
],
```

### Controller Design

File: `custom_addons/tx10_ai/controllers/bot_info.py`

```
Endpoint   POST /tx10_ai/bot_partner
Auth       auth="user"  (logged-in users only, no admin required)
Type       type="json"

Input      {} (empty JSON body — no parameters needed)

Logic
  1. Fetch bot partner via env.ref("tx10_ai.partner_ai_bot", raise_if_not_found=False)
  2. If not found → return {"partner_id": None, "error": "bot_not_configured"}
  3. Return {"partner_id": partner.id, "name": partner.name}

Error handling
  - No exceptions raised to client — errors returned as {"partner_id": None, "error": ...}
  - No rate-limit guard (read-only, cheap DB lookup, called once per page load)
  - No _guards.check_authorized — all authenticated users may open the chat

Class: Tx10AiBotInfoController(http.Controller)
Method: bot_partner(self, **kwargs)
Decorator: @http.route("/tx10_ai/bot_partner", type="json", auth="user", methods=["POST"])
```

`controllers/__init__.py` updated to:
```python
from . import _guards, bot_info, olg_proxy, openrouter_models
```

---

## Data Flow

### Error Path

```
User message arrives in discuss.channel
        |
        v
discuss_channel.py  →  chat._set_pending_agent_run()
                               |
                               v (cron or bus trigger)
                     Tx10AiChat._run_agent()
                               |
                               v
                     Tx10AiChat._do_agent_cycle()
                               |
                               v
                     Tx10AiService.chat_with_tools()
                               |
                    +----------+----------+
                    |                     |
               success                error_code
                    |                     |
                    v                     v
             content str        Tx10AiChat._format_error(error_code)
                    |                     |
                    +----------+----------+
                               |
                               v  (anti-silence: always non-empty)
                     discuss.channel.message_post(body=Markup)
                               |
                               v
                     tx10.ai.message created (role=assistant)
```

### Systray Path

```
Backend page load (OWL mount)
        |
        v
Tx10AiSystray.onWillStart()
        |
        | POST /tx10_ai/bot_partner
        v
Tx10AiBotInfoController.bot_partner()
        |
        | SELECT partner via env.ref("tx10_ai.partner_ai_bot")
        v
{"partner_id": 42, "name": "TeamX10 AI"}
        |
        v
this.partnerId = 42  →  <button> rendered in systray
        |
        | (user clicks)
        v
onClick()
        |
        | mail.store.openChat({partnerId: 42})
        v
Discuss DM channel with bot partner opened
        |
        | user types message
        v
discuss_channel  →  _run_agent()  →  (error path above if LLM fails)
```

---

## Dependencies Changed

### Files Added

| File | Purpose |
|------|---------|
| `custom_addons/tx10_ai/controllers/bot_info.py` | /tx10_ai/bot_partner endpoint |
| `custom_addons/tx10_ai/static/src/systray/tx10_ai_systray.js` | OWL systray component |
| `custom_addons/tx10_ai/static/src/systray/tx10_ai_systray.xml` | OWL template for systray |

### Files Removed

| File/Dir | Reason |
|----------|--------|
| `custom_addons/solar_ai/` (entire) | solar brand removed; replaced by tx10_ai systray |

### Files Modified

| File | Change |
|------|--------|
| `custom_addons/tx10_ai/models/tx10_ai_service.py` | Add `error_code` field to all 6 error return dicts in `chat()` and `chat_with_tools()` |
| `custom_addons/tx10_ai/models/tx10_ai_chat.py` | Add `_ERROR_USER_MESSAGES` dict, `_format_error()` method, anti-silence guarantee in `_run_agent` and `_do_agent_cycle` |
| `custom_addons/tx10_ai/controllers/__init__.py` | Add `bot_info` import |
| `custom_addons/tx10_ai/__manifest__.py` | Rename to "TeamX10 AI"; add systray JS/XML to assets |
| `custom_addons/tx10_ai/views/res_config_settings_views.xml` | Settings block label → "TeamX10 AI Assistant" |
| `custom_addons/solar_demo/__manifest__.py` | Remove `"solar_ai"` from `depends` |
| `docker-compose.yml` (or `.env`) | Remove `OPENROUTER_API_KEY` environment variable |

### Runtime Module State Change

| Action | Method |
|--------|--------|
| Uninstall `solar_ai` from DB | `ir.module.module.button_uninstall()` via `odoo-bin shell` |
| Update `tx10_ai` (picks up new assets + views) | `-u tx10_ai` on next server start |
| Update `solar_demo` (picks up removed dep) | `-u solar_demo` on next server start |
