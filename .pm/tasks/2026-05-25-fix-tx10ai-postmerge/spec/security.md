# Security: Fix tx10_ai post-merge issues

> Task: `2026-05-25-fix-tx10ai-postmerge`
> Module: `custom_addons/tx10_ai/`
> Date: 2026-05-25
> Reviewer: Claude Code (automated pre-implementation review)

---

## Threat Surface Changes

```
EXPANDS
  + New HTTP endpoint: GET /tx10_ai/bot_partner (auth="user") — returns partner_id integer
  + Error text now reaches the Discuss channel body (previously swallowed to log-only)
  + sudo() in message_post and tx10.ai.chat/message creates additional privilege-escalation surface

CONTRACTS
  - solar_ai module removed — eliminates /solar_ai/* controller routes, systray XHR
    calls, solar_ai.openrouter_api_key config param, and the solar_ai_chat/solar_ai_message
    model tables entirely (post-uninstall)
  - Error messages no longer silently hide failures — reduces risk of undetected
    misbehaviour being masked from operators

NET CHANGE: Small expansion. New endpoint is narrow-scope; error surfacing adds text to
the chat channel which is already accessible to channel members.
```

---

## S1. New Endpoint `/tx10_ai/bot_partner`

### Design intent (from spec, DoD item)

`controllers/bot_info.py` — JSON route returning `partner_id` (integer) of the bot
partner so the OWL systray can call `mail.store.openChat({partnerId})`.

### Auth level

`auth="user"` — requires an active Odoo session. Anonymous visitors cannot reach it.
Odoo's session middleware enforces this before the route handler executes.

### Data exposed

| Field | Type | Sensitivity |
|-------|------|-------------|
| `partner_id` | integer (DB id) | Non-sensitive — the bot partner is a public fixture (`active=False` res.partner seeded by `tx10_ai_bot.xml`). Its ID is already visible to any internal user via `discuss.channel` member lists. |
| `channel_id` (spec: "fallback") | integer or null | The user's own AI chat channel ID — they already own it; the record rule `rule_tx10_ai_chat_user` enforces `user_id = user.id`. Returning it here adds no new disclosure. |

### IDOR risk

**Low.** The endpoint returns a single global value (the bot partner id). It does not
accept a record id parameter, so there is no per-resource enumeration attack surface.
The bot partner has `active=False` which hides it from standard partner searches — the
endpoint is the deliberate disclosure path.

If `channel_id` is returned, it must be looked up via `self.env["tx10.ai.chat"].search([("user_id","=",request.env.uid)])` — scoped to the requesting user. The ORM record rule
(`rule_tx10_ai_chat_user`: `domain_force=[('user_id','=',user.id)]`) enforces this at
the database layer even if the application query omits the filter.

**Verify:** implementation must not accept a `user_id` query parameter that overrides
the lookup — always use `request.env.uid` (= `env.user.id` after `auth="user"`
processing).

### CSRF

The new route will use `type="json"`, consistent with the existing `olg_proxy.py`
routes. Odoo's JSON-RPC dispatcher (`odoo/http.py:csrf_token` path) **does not apply
form-based CSRF to `type="json"` routes** because JSON endpoints require
`Content-Type: application/json` which browsers cannot set from a cross-origin form
submission (CORS preflight blocks it). The `csrf=False` annotation on existing routes
(`olg_proxy.py:44,72`) is therefore safe for JSON-only endpoints.

**Risk if `type="http"` is used instead:** a `type="http"` route without CSRF would be
vulnerable to cross-site form POST. The implementation MUST use `type="json"`.

---

## S2. Error Information Disclosure

### What non-admins see vs. admins

```
User class          | Message body
--------------------|----------------------------------------------
Non-admin           | Friendly localized string only
                    | e.g. "Сервіс ШІ тимчасово недоступний."
Admin (group_system)| Friendly text + " — код: <error_code>"
                    | e.g. "... — код: http_error"
```

Implemented via `_format_error(code, user)` in `tx10_ai_chat.py` (planned). The
error code is a stable machine token from `_ERROR_USER_MESSAGES` dict — not a stack
trace, not an internal URL, not a model name.

### Group check correctness — critical analysis

The spec states: `_format_error` checks `self.user_id.has_group('base.group_system')`.

`self` is `tx10.ai.chat`. The field `user_id` is declared:

```python
# tx10_ai_chat.py line 43
user_id = fields.Many2one("res.users", required=True, default=lambda s: s.env.user, readonly=True)
```

`user_id` is set at chat creation time in `_init_tx10_ai_chat`:

```python
# res_users.py line 41
self.env["tx10.ai.chat"].sudo().create({"user_id": self.id, ...})
```

`self.id` here is the human user who triggered `_on_webclient_bootstrap`. **`user_id`
always holds the human requester, not the bot.** The bot has no `res.users` record —
it is a `res.partner` only (`tx10_ai_bot.xml`).

When `_run_agent` runs inside `_cron_run_pending_chats`, `self` is the chat record and
`self.user_id` is still the original human owner (set at creation, readonly). The cron
runs as the `cron user` (superuser / UID 1 in standard Odoo), but the group check reads
`self.user_id` — the human — not `self.env.user` (which would be the cron superuser).

**Conclusion: the identity used for the group check is correct.** If `env.user` were
used instead, every cron-run error would always show the admin suffix (cron runs as
superuser), which would be wrong.

**Verify:** implementation must call `self.user_id.has_group(...)`, never
`self.env.user.has_group(...)` inside `_format_error`.

### What is NOT exposed to non-admins

The following must never appear in user-facing error text:

```
- Stack traces
- Internal model names (e.g. tx10.ai.chat, ir.config_parameter)
- SQL or ORM error strings
- OpenRouter HTTP response bodies (exc.response.text)
- API key presence/absence confirmation beyond "not configured"
- Internal file paths or line numbers
```

The current `tx10_ai_service.py` logs `exc.response.text[:300]` to `_logger.error` —
this is server-side only and acceptable.

### Error code token leak risk

The admin-only suffix `— код: no_api_key` exposes a machine token. This is intentional
for operator debuggability. The tokens are enumeratable from the source (`_ERROR_USER_MESSAGES` keys) so they carry no additional secret — only operational state
confirmation.

---

## S3. `sudo()` Usage in `message_post`

### Where `sudo()` is used

```
File                    | Call site                                           | Reason
------------------------|-----------------------------------------------------|-----------------------
tx10_ai_chat.py:110     | self.channel_id.sudo().message_post(...)            | Bot posts as author_id=bot_partner.id; channel may have write rules the cron user (or bot) does not satisfy under normal ACL
tx10_ai_chat.py:117     | self.env["tx10.ai.message"].sudo().create(...)      | Cron context; message ownership is enforced by chat_id FK, not by session user
discuss_channel.py:56   | self.env["tx10.ai.message"].sudo().create(...)      | Hook runs in caller's env; avoids ACL interference when the message hook fires
discuss_channel.py:63   | chat.sudo().write({"pending_agent_run": True})      | Cron flag; caller may not have write on tx10.ai.chat
res_users.py:41         | self.env["tx10.ai.chat"].sudo().create(...)         | Bootstrap; the web-client user has no write ACL on tx10.ai.chat by design
res_users.py:51         | channel.sudo().message_post(...)                    | Welcome message posted as bot partner; same pattern as above
```

### Scope assessment

`sudo()` in Odoo drops to superuser only for **the current recordset operation** — it
does not persist across method calls. All usages above are:

1. Narrow: one ORM call each.
2. Scoped: the data written is either (a) owned by the current user (via `user_id` FK
   hard-coded at create time) or (b) a bot-authored message where no user-owned data
   is modified.
3. No user-controlled values bypass validation: field whitelists in `_validate_write_values`
   and record rules run at query time against the DB; `sudo()` on `message_post` does not
   bypass Odoo's HTML sanitizer on the `body` field.

### Risk: privilege escalation via `message_post` body

`sudo()` elevates the **ORM user** but the `body` field in `mail.message` is passed
through Odoo's HTML purifier (`html_sanitize`) unconditionally by the mail module before
storage. The bot's `response_text` is built using `Markup.escape()` throughout
`_do_agent_cycle` — user-supplied content is escaped before being joined into the final
`Markup` string. Server-constructed HTML links (`Markup("<a ...>%s</a>") % (...)`) use
positional `%` which escapes the interpolated values.

**No XSS vector is introduced by the `sudo()` calls.**

### Residual concern: `cron.sudo()._trigger()`

`discuss_channel.py:67` calls `cron.sudo()._trigger()` to wake the cron. This is the
standard Odoo pattern for triggering a cron from a non-cron context and carries no
unusual risk. The cron record (`tx10_ai.ir_cron_run_agent`) is a fixed server-side
fixture; the trigger only marks it for early execution — no user-controlled data flows
into the cron trigger call.

---

## S4. `solar_ai` Removal Security Impact

### Attack surface eliminated

```
Removed                                     | Security benefit
--------------------------------------------|------------------------------------------
/solar_ai/chat (HTTP controller)            | Eliminates AI proxy route for solar_ai users
solar_ai.openrouter_api_key (config param)  | Eliminates a second plaintext API key in DB
solar_ai systray JS (ai_assistant_systray)  | Eliminates XHR calls from browser to removed route
solar_ai settings block (ResConfigSettings) | Eliminates field that reads/writes config param
solar_ai_chat, solar_ai_message models      | Tables removed (post-uninstall migration)
```

### Residual data after uninstall

Odoo does NOT automatically delete `ir.config_parameter` rows when a module is
uninstalled unless the module's uninstall hook explicitly removes them. The
`solar_ai.openrouter_api_key` and `solar_ai.default_model` params will remain as orphan
rows in `ir_config_parameter` after `solar_ai` is uninstalled.

**Risk:** The API key (a sensitive credential) persists in the database orphaned. Any
admin who knows the param key name can read it via Settings > Technical > Parameters.

**Mitigation required:** The PR should include a `post_uninstall` hook in `solar_ai`
(or a `tx10_ai` upgrade migration) that calls:

```python
self.env["ir.config_parameter"].sudo().search(
    [("key", "like", "solar_ai.%")]
).unlink()
```

If `solar_ai` is removed via `git rm` rather than Odoo's module manager, the orphan
params will not be cleaned automatically. Document this in the deployment checklist.

### Config param namespace collision

`solar_ai.openrouter_api_key` and `tx10_ai.openrouter_api_key` are separate keys — no
collision. After solar_ai removal, `tx10_ai.*` params are the only AI-related entries.

---

## S5. i18n Strings Security

### XSS in translated strings

Error messages are marked with `_()` or `_lt()` for i18n. In Odoo 19:

- `_()` returns a plain `str` — **must be wrapped with `Markup.escape()`** before
  joining into a `Markup` context.
- `_lt()` returns a lazy translation proxy — same requirement.
- `Markup(translated_string)` without escaping would treat the translation as trusted
  HTML — a translator could inject `<script>` tags via a malicious `.po` file.

**Required pattern** (correct):

```python
# Safe: escape the translated string, then join into Markup
msg = Markup.escape(_("AI service temporarily unavailable."))
if is_admin:
    msg = msg + Markup(" — код: ") + Markup.escape(code)
```

**Prohibited pattern** (XSS risk):

```python
# UNSAFE: wrapping translation in Markup trusts the translator
msg = Markup(_("AI service temporarily unavailable."))
```

### Odoo chatter sanitization chain

Even if a `Markup` string somehow contained HTML tags, `mail.message.body` is stored
through `html_sanitize` (called by the mail module's `message_post` before write).
The sanitizer strips disallowed tags and attributes. This is a defense-in-depth layer —
it does not justify skipping `Markup.escape()` at the construction site.

### `.po` file injection

`uk.po` entries for error strings are plain text values without HTML. Translators
should be instructed (via developer notes in the `.po` source comments) that HTML is
not permitted in these strings. A CI lint step (`msgfmt --check`) should be run on
`.po` files to catch malformed entries.

---

## Risk Summary

```
Risk                              | Likelihood | Impact   | Mitigation
----------------------------------|------------|----------|-------------------------------------------------
IDOR on /tx10_ai/bot_partner      | Very Low   | Low      | No id param; returns global bot id + own channel
CSRF on new JSON endpoint         | Very Low   | Medium   | type="json" blocks cross-origin form POST
Wrong user in group check         | Low        | Medium   | Verified: user_id = human owner, readonly field
XSS via translated error string   | Low        | High     | Use Markup.escape(_(...)) — see S5
XSS via message_post body         | Very Low   | High     | Markup.escape() used throughout; chatter sanitizes
API key persists after uninstall  | Medium     | Medium   | Add post_uninstall hook or deployment cleanup step
Rate limit bypass (multi-worker)  | Medium     | Low      | Known; documented in _guards.py; acceptable for now
sudo() scope creep                | Very Low   | High     | All sudo() calls are single-op, narrow scope
```

---

## Checklist — Verify Before PR Merge

### Endpoint (`/tx10_ai/bot_partner`)

- [ ] Route is `type="json"`, not `type="http"`
- [ ] `auth="user"` — confirmed no `auth="none"` or `auth="public"`
- [ ] Channel lookup uses `request.env.uid` (not a user-supplied parameter)
- [ ] Response contains only `partner_id` (int) and optionally `channel_id` (int or
      null) — no partner name, email, or other PII
- [ ] No `sudo()` on the partner lookup (bot partner is `active=False` but readable
      via `env.ref`; no elevated access needed)

### Error formatting (`_format_error`)

- [ ] Uses `self.user_id.has_group("base.group_system")` — NOT `self.env.user.has_group`
- [ ] User-facing text wrapped with `Markup.escape(_lt(...))` before joining into Markup
- [ ] Admin suffix is ` — код: {code}` appended AFTER the escaped friendly text
- [ ] No stack trace, model name, SQL fragment, or internal URL in any branch
- [ ] `_ERROR_USER_MESSAGES` covers: `no_api_key`, `http_error`, `network_error`,
      `empty_choices`, `terminated_content_filter`, `terminated_length`, `unknown`

### Anti-silence guarantee

- [ ] `_run_agent` guard changed from `if response_text and self.channel_id` to
      `if self.channel_id` (response_text is guaranteed non-empty by `_format_error`)
- [ ] Exception handler in `_run_agent` sets `response_text` to a non-empty Markup
      fallback before reaching the `message_post` call
- [ ] `message_post` is always reached when `self.channel_id` exists — confirmed by
      reading the finally/except flow

### `sudo()` audit

- [ ] No `sudo()` call operates on a model where user-supplied values (from LLM output
      or HTTP body) are written without prior whitelist validation
- [ ] `channel_id.sudo().message_post(body=response_text)` — confirm `response_text`
      is built entirely from server-side Markup, not raw user/LLM strings

### `solar_ai` removal

- [ ] Deployment runbook includes step: verify `solar_ai.openrouter_api_key` param
      deleted from `ir_config_parameter` (manual SQL or migration script)
- [ ] `solar_demo/__manifest__.py` — `solar_ai` removed from `depends`
- [ ] `grep -ri "solar_ai" custom_addons/ --include="*.py" --include="*.xml" --include="*.js"` returns zero matches

### i18n

- [ ] All `_ERROR_USER_MESSAGES` values use `_lt()` (lazy translation, safe at module
      import time)
- [ ] `uk.po` contains `msgid`/`msgstr` entries for each error message string
- [ ] No `Markup(_(…))` patterns — only `Markup.escape(_(…))` or `Markup.escape(_lt(…))`
