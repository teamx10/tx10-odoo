# Technical: Fix tx10_ai post-merge issues

---

## Implementation Order

```
1. B1  — Uninstall solar_ai from the running DB (shell command).
          Must happen FIRST — solar_demo depends on it; removing solar_ai
          from the FS while it is installed in the DB causes a broken state.

2. B2  — solar_demo/__manifest__.py: remove "solar_ai" from depends.
          Allows solar_demo to load after solar_ai is gone.

3. B5  — Remove OPENROUTER_API_KEY from docker-compose.yml.
          No code depends on this env var (tx10_ai reads from ir.config_parameter).

4. A1  — tx10_ai_service.py: add error_code to every error return dict.
          Must land before A2 so chat.py can rely on the new key.

5. A2  — tx10_ai_chat.py: add _ERROR_USER_MESSAGES, _format_error(), fix guards.
          Depends on A1 error_code keys being stable.

6. A3  — i18n/uk.po: add Ukrainian strings for _ERROR_USER_MESSAGES.
          Depends on A2 string literals being finalized.

7. B4  — __manifest__.py name change + assets registration for systray.
          Independent, but placed here to bundle with the frontend work.

8. B4b — res_config_settings_views.xml block title change.
          Trivial string rename, bundled with B4.

9. B2c — Create controllers/bot_info.py.
          Prerequisite for the systray component that calls it.

10. B3  — Create static/src/systray/tx10_ai_systray.js + .xml.
           Depends on B2c (the RPC endpoint it calls).

11. git rm -r custom_addons/solar_ai/
           Last step — after the DB uninstall in B1 is done.
```

---

## A1. tx10_ai_service.py changes

### Current gap

`chat()` returns `{"content": "", "usage": {}}` on no-key — no `error` key at all.
`chat_with_tools()` already has `error: "no_api_key"` on no-key (line 134) but uses
`str(exc)` for HTTP/network errors — callers cannot branch on error type.

Both methods use free text or the exc string as `error`; there is no typed `error_code`.

### Required changes — add `error_code` to every error branch

#### `chat()` method

| Condition | Current return | After |
|-----------|---------------|-------|
| no API key | `{"content":"","usage":{}}` (no error key) | add `"error":"no_api_key"`, `"error_code":"no_api_key"` |
| `httpx.HTTPStatusError` | `"error": str(exc)` | add `"error_code": "http_error"` |
| `httpx.RequestError` | `"error": str(exc)` | add `"error_code": "network_error"` |
| empty choices | `"error": "empty_choices"` | add `"error_code": "empty_choices"` |

Note: `chat()` does not produce `length` / `content_filter` branches — those only
occur in `chat_with_tools()` which already sets `error: f"terminated_{finish_reason}"`.

Return dict shapes after change:

```python
# no key
return {
    "content": "",
    "usage": {},
    "error": "no_api_key",
    "error_code": "no_api_key",
}

# HTTPStatusError
return {
    "content": "",
    "usage": {},
    "elapsed_ms": 0,          # add for symmetry (not currently present)
    "error": str(exc),
    "error_code": "http_error",
}

# RequestError
return {
    "content": "",
    "usage": {},
    "elapsed_ms": 0,
    "error": str(exc),
    "error_code": "network_error",
}

# empty choices
return {
    "content": "",
    "usage": data.get("usage", {}),
    "elapsed_ms": elapsed_ms,
    "error": "empty_choices",
    "error_code": "empty_choices",
}
```

#### `chat_with_tools()` method

| Condition | Current `error` value | Add `error_code` |
|-----------|----------------------|------------------|
| no API key | `"no_api_key"` | `"error_code": "no_api_key"` |
| `httpx.HTTPStatusError` | `str(exc)` | `"error_code": "http_error"` |
| `httpx.RequestError` | `str(exc)` | `"error_code": "network_error"` |
| empty choices | `"empty_choices"` | `"error_code": "empty_choices"` |
| `finish_reason == "length"` | `"terminated_length"` | `"error_code": "terminated_length"` |
| `finish_reason == "content_filter"` | `"terminated_content_filter"` | `"error_code": "terminated_content_filter"` |

The last two are produced at line 224–225:
```python
if finish_reason in ("length", "content_filter"):
    result["error"] = f"terminated_{finish_reason}"
    result["error_code"] = f"terminated_{finish_reason}"   # ADD
```

All other branches get `error_code` added alongside the existing `error` key.

---

## A2. tx10_ai_chat.py changes

### Module-level imports to add

```python
from odoo.tools.translate import LazyTranslate

_lt = LazyTranslate(__name__)
```

### `_ERROR_USER_MESSAGES` dict

Place at module level, after `_logger`, before `SYSTEM_PROMPT_TEMPLATE`:

```python
_ERROR_USER_MESSAGES = {
    "no_api_key": _lt(
        "AI is not configured yet. "
        "Please ask your administrator to set the OpenRouter API key."
    ),
    "http_error": _lt(
        "The AI service returned an error. "
        "Please try again later or contact your administrator."
    ),
    "network_error": _lt(
        "Could not reach the AI service. "
        "Check the server's internet connection and try again."
    ),
    "empty_choices": _lt(
        "The AI returned an empty response. "
        "Your message may have been filtered. Please rephrase and try again."
    ),
    "terminated_length": _lt(
        "The AI response was cut off because it exceeded the length limit."
    ),
    "terminated_content_filter": _lt(
        "The AI response was blocked by a content filter. "
        "Please rephrase your message."
    ),
    "unknown": _lt(
        "An unexpected error occurred. Please try again or contact your administrator."
    ),
}
```

### `_format_error()` method

Add to `Tx10AiChat` class, after `_reject_action`, before `_build_messages`:

```python
def _format_error(self, error_code, exc_name=None):
    """Return a user-visible Markup string for an LLM error.

    Admins (base.group_system) also see the raw error_code appended.
    exc_name is the exception class name, shown to admins for unknown errors.
    """
    base = _ERROR_USER_MESSAGES.get(
        error_code,
        _ERROR_USER_MESSAGES["unknown"],
    )
    text = Markup.escape(str(base))
    if self.user_id.has_group("base.group_system"):
        detail = error_code
        if exc_name:
            detail = f"{error_code} ({exc_name})"
        text = text + Markup(f"\n\n— код: {Markup.escape(detail)}")
    return text
```

Signature: `def _format_error(self, error_code: str, exc_name: str | None = None) -> Markup`

### `_do_agent_cycle` — error branch change

Current (line 188–189):
```python
if llm_result.get("error") or llm_result.get("finish_reason") == "stop":
    return Markup.escape(llm_result.get("content") or "")
```

After change:
```python
if llm_result.get("error"):
    error_code = llm_result.get("error_code") or "unknown"
    return self._format_error(error_code)

if llm_result.get("finish_reason") == "stop":
    return Markup.escape(llm_result.get("content") or "")
```

Rationale: the original merged `error` and `finish_reason == "stop"` into one branch.
Separating them means a successful stop returns actual content; an error returns the
user-friendly message instead of an empty string.

### `_run_agent` — except block change

Current (line 103–104):
```python
except Exception:
    _logger.exception("tx10_ai: _do_agent_cycle failed for chat %s", self.id)
    response_text = Markup("Вибачте, сталася помилка. Спробуйте ще раз.")
```

After change:
```python
except Exception as exc:
    _logger.exception("tx10_ai: _do_agent_cycle failed for chat %s", self.id)
    response_text = self._format_error("unknown", exc_name=type(exc).__name__)
```

### `_run_agent` — posting guard change

Current (line 109):
```python
if response_text and self.channel_id:
```

After change:
```python
if self.channel_id:
```

Rationale: error messages from `_format_error` are always non-empty Markup, so the
truthiness gate works. But an empty `response_text` (e.g. from a successful LLM call
that returned `""`) would be silently dropped. Removing the gate ensures errors are
always posted. The `self.channel_id` guard is kept — without a channel there is nowhere
to post.

---

## A3. i18n: tx10_ai/i18n/uk.po entries needed

The `i18n/` directory does not currently exist in the module. Create
`custom_addons/tx10_ai/i18n/uk.po` with the following strings:

```po
# Ukrainian translation for tx10_ai
# Copyright (C) TeamX10
msgid ""
msgstr ""
"Content-Type: text/plain; charset=UTF-8\n"
"Content-Transfer-Encoding: 8bit\n"

msgid ""
"AI is not configured yet. "
"Please ask your administrator to set the OpenRouter API key."
msgstr ""
"AI ще не налаштовано. "
"Зверніться до адміністратора для встановлення ключа OpenRouter API."

msgid ""
"The AI service returned an error. "
"Please try again later or contact your administrator."
msgstr ""
"Сервіс AI повернув помилку. "
"Спробуйте пізніше або зверніться до адміністратора."

msgid ""
"Could not reach the AI service. "
"Check the server's internet connection and try again."
msgstr ""
"Не вдалося з'єднатися з сервісом AI. "
"Перевірте підключення до інтернету та спробуйте ще раз."

msgid ""
"The AI returned an empty response. "
"Your message may have been filtered. Please rephrase and try again."
msgstr ""
"AI повернув порожню відповідь. "
"Ваше повідомлення могло бути відфільтровано. Перефразуйте та спробуйте знову."

msgid "The AI response was cut off because it exceeded the length limit."
msgstr "Відповідь AI обрізано — вона перевищила допустиму довжину."

msgid ""
"The AI response was blocked by a content filter. "
"Please rephrase your message."
msgstr ""
"Відповідь AI заблоковано фільтром контенту. "
"Перефразуйте ваше повідомлення."

msgid ""
"An unexpected error occurred. Please try again or contact your administrator."
msgstr ""
"Виникла непередбачена помилка. "
"Спробуйте ще раз або зверніться до адміністратора."
```

---

## B1. solar_ai uninstall sequence

solar_ai is currently installed in the running database. Removing the filesystem
directory before uninstalling causes Odoo to log errors on startup. Correct order:

```
Step 1 — Shell-uninstall via odoo-bin (preferred, runs within the transaction)

./odoo-bin shell -d <dbname> --addons-path=addons,odoo/addons,custom_addons
>>> env['ir.module.module'].search([('name', '=', 'solar_ai')]).button_immediate_uninstall()
>>> env.cr.commit()
>>> exit()

Step 2 — Verify uninstall succeeded

./odoo-bin shell -d <dbname> --addons-path=addons,odoo/addons,custom_addons
>>> env['ir.module.module'].search([('name', '=', 'solar_ai')]).state
# Must print 'uninstalled'
>>> exit()

Step 3 — Remove filesystem directory

git rm -r custom_addons/solar_ai/

Step 4 — Remove solar_ai from solar_demo depends (see B4 / manifest change below).
          Do this BEFORE committing the git rm so the module load order stays consistent.
```

Alternative if shell is not accessible (Docker):
```bash
docker compose exec odoo ./odoo-bin shell -d isolar \
  --addons-path=/mnt/extra-addons,/usr/lib/python3/dist-packages/odoo/addons \
  -e "env['ir.module.module'].search([('name','=','solar_ai')]).button_immediate_uninstall(); env.cr.commit()"
```

---

## B2. bot_info.py controller

**File:** `custom_addons/tx10_ai/controllers/bot_info.py`

```
Route:     /tx10_ai/bot_partner
Type:      json  (POST, Odoo JSON-RPC convention)
Auth:      user  (requires authenticated session)
Methods:   POST  (implicit for type="json")
CSRF:      not needed for type="json" (framework handles it)
```

```python
import logging

from odoo import http
from odoo.http import request

_logger = logging.getLogger(__name__)


class Tx10AiBotInfo(http.Controller):

    @http.route("/tx10_ai/bot_partner", type="json", auth="user")
    def bot_partner(self, **kwargs):
        """Return the partner_id of the tx10_ai bot for use by the systray."""
        bot = request.env.ref(
            "tx10_ai.partner_ai_bot", raise_if_not_found=False
        )
        if not bot:
            _logger.warning("tx10_ai: partner_ai_bot record not found")
            return {"partner_id": None}
        # sudo() needed: partner_ai_bot has active=False (archived),
        # regular users cannot browse inactive partners without sudo.
        return {"partner_id": bot.sudo().id}
```

Return shapes:
```
Success:   {"partner_id": <int>}
Not found: {"partner_id": null}
```

Add to `controllers/__init__.py`:
```python
from . import _guards, bot_info, olg_proxy, openrouter_models
```

---

## B3. Systray component

### JS: `custom_addons/tx10_ai/static/src/systray/tx10_ai_systray.js`

Pattern modeled on `addons/mail/static/src/core/web/open_chat_hook.js` and
`addons/mail/static/src/discuss/core/common/channel_member_list.js`.

```javascript
/** @odoo-module */
import { Component, onWillStart } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { rpc } from "@web/core/network/rpc";

export class Tx10AiSystray extends Component {
    static template = "tx10_ai.Tx10AiSystray";
    static props = {};

    setup() {
        this.store = useService("mail.store");
        this.botPartnerId = null;

        onWillStart(async () => {
            try {
                const result = await rpc("/tx10_ai/bot_partner");
                this.botPartnerId = result?.partner_id ?? null;
            } catch (e) {
                // Non-fatal: button will be inert if bot partner cannot be resolved.
                console.warn("tx10_ai: could not resolve bot partner id", e);
            }
        });
    }

    onClick() {
        if (this.botPartnerId) {
            this.store.openChat({ partnerId: this.botPartnerId });
        }
    }
}

registry.category("systray").add("tx10_ai.systray", {
    Component: Tx10AiSystray,
}, { sequence: 5 });
```

Key design decisions:
- `rpc` is imported directly from `@web/core/network/rpc` (not a service) — this is
  the Odoo 19 pattern for standalone JSON-RPC calls (see `addons/web/static/src/core/user.js:3`).
- `useService("mail.store")` gives access to `openChat({ partnerId })` which navigates
  to or opens the DM channel with the bot partner.
- `botPartnerId` is stored as a plain property, not reactive state — it is set once
  in `onWillStart` before first render.

### XML: `custom_addons/tx10_ai/static/src/systray/tx10_ai_systray.xml`

```xml
<?xml version="1.0" encoding="utf-8"?>
<templates xml:space="preserve">
    <t t-name="tx10_ai.Tx10AiSystray">
        <div class="o-tx10-ai-systray d-flex align-items-center">
            <button
                class="o-tx10-ai-systray-btn btn"
                t-on-click="onClick"
                aria-label="TeamX10 AI"
                title="TeamX10 AI"
                t-att-disabled="!botPartnerId"
            >
                <i class="fa fa-lg fa-comments" role="img" aria-hidden="true"/>
            </button>
        </div>
    </t>
</templates>
```

---

## Font Awesome Version Check

**Result: Odoo 19 bundles Font Awesome 4.7.0 (FA4), not FA5.**

Evidence:
```
addons/web/static/src/libs/fontawesome/css/font-awesome.css
  Line 1: "Based on Font Awesome 4.7.0 by @davegandy"
```

FA4 icon availability:
```
fa-comments   — EXISTS (verified in font-awesome.css: ".fa-comments:before")
fa-robot      — DOES NOT EXIST in FA4 (fa-robot is FA5 / FA6 only)
fa-android    — exists in FA4 (used by solar_ai's old systray)
```

**Decision: use `fa fa-comments` for the systray icon.**

`fa-robot` would render as a broken icon box in Odoo 19. `fa-comments` is thematically
correct (chat with the AI bot) and confirmed present in FA 4.7.0.

---

## B4. Manifest and view changes

### `custom_addons/tx10_ai/__manifest__.py`

Change 1 — module name:
```python
# Before
"name": "TX10 AI",

# After
"name": "TeamX10 AI",
```

Change 2 — register systray assets in `web.assets_backend`:
```python
"assets": {
    "web.assets_backend": [
        "tx10_ai/static/src/components/model_select_widget.js",
        "tx10_ai/static/src/components/model_select_widget.xml",
        "tx10_ai/static/src/components/model_select_widget.scss",
        "tx10_ai/static/src/systray/tx10_ai_systray.js",   # ADD
        "tx10_ai/static/src/systray/tx10_ai_systray.xml",  # ADD
    ],
},
```

### `custom_addons/tx10_ai/views/res_config_settings_views.xml`

```xml
<!-- Before -->
<block title="TX10 AI Assistant" id="tx10_ai_assistant">

<!-- After -->
<block title="TeamX10 AI Assistant" id="tx10_ai_assistant">
```

### `custom_addons/solar_demo/__manifest__.py`

```python
# Before
"depends": ["solar_project", "solar_ai"],

# After
"depends": ["solar_project"],
```

---

## B5. docker-compose change

**File:** `docker-compose.yml`

Remove the `OPENROUTER_API_KEY` line from the `odoo` service `environment` block:

```yaml
# Remove this line:
      OPENROUTER_API_KEY: ${OPENROUTER_API_KEY:-}
```

Rationale: `tx10_ai` reads its API key exclusively from `ir.config_parameter`
(`tx10_ai.openrouter_api_key`), set through the Odoo Settings UI. The env var is
never read by any Python code in the module — it was a legacy leftover from the
`solar_ai` era. Removing it avoids misleading operators who might assume setting
this env var configures the AI.

The `# OpenRouter key — empty = AI features inactive, no crash` comment above it
should also be removed.
