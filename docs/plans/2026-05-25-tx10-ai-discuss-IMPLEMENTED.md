# tx10_ai Implementation Log

**Date:** 2026-05-25
**Branch:** feat/tx10-ai-discuss
**Base:** 19.0
**PR target:** develop

---

## Goal

Migrate `solar_ai` to new `tx10_ai` module where the AI assistant lives as a native Odoo Discuss bot. User writes in a DM channel → bot processes asynchronously via `ir.cron` → responds with `mail.message` containing clickable `data-oe-model/data-oe-id` HTML links → confirms write actions via natural language in chat.

---

## Delivered

### Module structure (`custom_addons/tx10_ai/`)

**Models (7 files):**
- `tx10_ai_service.py` — `tx10.ai.service`: LLM client (OpenRouter/httpx), `chat()`, `chat_with_tools()`
- `tx10_ai_message.py` — `tx10.ai.message`: conversation message with `role`, `status`, `proposed_action`, CAS guards
- `tx10_ai_chat.py` — `tx10.ai.chat`: conversation with `channel_id`, `pending_agent_run`, async agent cycle, budget tracking
- `tx10_ai_agent.py` — `tx10.ai.agent`: tool registry, HTML nav links, whitelist validation, no `_CLIENT_TOOLS`
- `res_config_settings.py` — settings model: API key + model selection via `config_parameter`
- `discuss_channel.py` — `discuss.channel` inherit: `_message_post_after_hook` captures DM messages
- `res_users.py` — `res.users` inherit: `_on_webclient_bootstrap` auto-creates DM channel + welcome message

**Controllers (3 files):**
- `_guards.py` — `check_authorized`, sliding-window rate limiter
- `olg_proxy.py` — OLG proxy at `/tx10_ai/olg/` routes (html_editor AI buttons)
- `openrouter_models.py` — `/tx10_ai/openrouter/models` with 24h cache

**Data files:**
- `tx10_ai_bot.xml` — `partner_ai_bot` (inactive partner)
- `config_params.xml` — seed URL + model params (`noupdate="1"`)
- `ir_cron.xml` — `ir_cron_run_agent`, 1-minute interval, indefinite

**Tests (5 files, 72 total, 48 post-install):**
- `test_tx10_ai.py` — service, models, chat, data, OLG proxy (22 tests)
- `test_tx10_ai_agent.py` — agent capabilities (12 tests)
- `test_tx10_ai_discuss.py` — Discuss hook, cron cycle, NL confirm, bootstrap (9 tests)
- `test_tx10_ai_models_endpoint.py` — guard unit tests (3 tests)
- `test_tx10_ai_settings.py` — config settings (2 tests)

---

## Key patterns established

| Pattern | Location | Purpose |
|---------|----------|---------|
| Anti-loop guard | `discuss_channel.py:25` | Skip bot-authored messages in hook |
| CAS pending flag | `tx10_ai_chat.py:75-81` | `UPDATE...WHERE flag=TRUE` + rowcount==0 early return |
| Markup.escape() | `tx10_ai_chat.py:192` | All LLM-generated content sanitized for XSS |
| `env(user=self.user_id)` | `tx10_ai_chat.py:288` | User-bound env for confirmed action execution |
| `with_user(self.id)` | `res_users.py:37` | Unambiguous user ID for `_get_or_create_chat` |
| `_trigger()` in try/except | `discuss_channel.py:65-69` | Safe cron trigger — never aborts user's message_post |
| `noupdate="1"` on security | `tx10_ai_security.xml:1` | Prevents rule reset on `-u tx10_ai` |
| HTML data-oe links | `tx10_ai_agent.py` | Zero custom JS — native Odoo record nav |
| CONFIRM_TOOLS | `tx10_ai_chat.py:16-33` | LLM interprets NL "yes/no" via dedicated tools |

---

## Deviations from plan

| Plan says | Actual | Reason |
|-----------|--------|--------|
| `self.env["discuss.channel"]._get_or_create_chat(...)` | `.with_user(self.id)._get_or_create_chat(...)` | Odoo 19 auto-adds `env.user.partner_id` → 3-person channel without user binding |
| `self.env.with_user(self.user_id)` in `_execute_confirmed_action` | `self.env(user=self.user_id)` | `Environment` has no `with_user`; `env(user=...)` is the correct API |
| `numbercall=-1` in `ir_cron.xml` | Field omitted | Field removed in Odoo 17+ |
| `<odoo>` in security XML | `<odoo noupdate="1">` | Prevent rule reset on module update |
| Manager-only ACL in CSV | Added user-group rows | Manager-only left regular users unable to create chats |
| `Markup(response_text)` in response building | `Markup.escape(text)` + `Markup("").join(parts)` | `Markup(untrusted)` is XSS-unsafe; escape is required |
| `tx10_ai_state` field no default | Added `default="not_initialized"` | Implicit NULL handling via `in (False, ...)` is fragile |

---

## Verification

- **solar_ai residue:** 0 matches in `custom_addons/tx10_ai/`
- **Tests:** 48 post-install, 0 failed, 0 errors
- **Module install:** no ERRORs (1 cosmetic deprecation warning on `@route(type='json')` — pre-existing Odoo 19 deprecation)
- **gitnexus:** LOW risk, no unexpected blast radius

---

## Commits

```
f52ca62 [ADD] tx10_ai: migrate solar_ai tests + IDOR, CAS, dangling tool_calls, TOCTOU tests
ae8d169 [FIX] tx10_ai: remove solar_ai brand string in olg_proxy, add tearDown for rate limit test
2ff9cbb [ADD] tx10_ai: port controllers (_guards, olg_proxy, openrouter_models)
ed98be8 [FIX] tx10_ai: privilege boundary clarity and test assertion reliability in res_users
47164280 [ADD] tx10_ai: res_users bootstrap — auto-create DM channel with bot
d2042f2 [FIX] tx10_ai: html.unescape in _strip_html, sudo chat search, safe _trigger()
1aa44fe [ADD] tx10_ai: discuss_channel hook, NL confirm/reject tests
7a0312c [FIX] tx10_ai: noupdate on security rules, add user-group ACL, null guard in formatPrice
1c3f297 [ADD] tx10_ai: security rules, settings model, views, model_select_widget
d596f65 [DOC] tx10_ai: add noupdate rationale comment to config_params.xml
eff0ef2 [ADD] tx10_ai: bot partner, config params, cron record
0fce4ba [FIX] tx10_ai: remove solar.document from registry, drop redundant capability check
6bf3863 [ADD] tx10_ai: agent model — HTML nav links, no _CLIENT_TOOLS
a716c2d [FIX] tx10_ai: safe Markup escaping for LLM output + null channel_id guard
6f43593 [FIX] tx10_ai: add rowcount guard in _reject_action CAS pattern
650c8a5 [ADD] tx10_ai: full chat model with async agent cycle, confirm/reject, _build_messages
309abbc [ADD] tx10_ai: port message model (tx10.ai.message) + minimal chat stub
566a546 [REF] tx10_ai: remove solar domain dead code from tx10_ai_service
566a546 [ADD] tx10_ai: port LLM service model (tx10.ai.service)
ce1692f [ADD] tx10_ai: module scaffold (manifest, __init__ files, empty stubs)
8b74dd8 [ADD] tx10_ai: init feature branch (from feat/solar-ai-settings)
```
