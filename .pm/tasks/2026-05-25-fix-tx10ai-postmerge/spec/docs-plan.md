# Docs Plan: Fix tx10_ai post-merge issues

**Task:** 2026-05-25-fix-tx10ai-postmerge
**Branch:** feat/tx10-ai-discuss
**Date:** 2026-05-25

---

## Documents to Update

| Document | Change needed | Priority | Notes |
|----------|--------------|---------|-------|
| `custom_addons/tx10_ai/__manifest__.py` | `"name": "TX10 AI"` → `"TeamX10 AI"` (line 2 only; technical id `tx10_ai` stays) | HIGH | User-facing label shown in Apps list and Settings |
| `custom_addons/tx10_ai/views/res_config_settings_views.xml` | `<block title="TX10 AI Assistant"` → `"TeamX10 AI Assistant"` | HIGH | Shown in Settings UI; must match branding decision |
| `custom_addons/solar_demo/__manifest__.py` | `depends`: remove `"solar_ai"` from the list (line 7: `["solar_project", "solar_ai"]` → `["solar_project"]`) | HIGH | Required before `solar_ai` deletion; break the dependency chain first |
| `docker-compose.yml` | Remove `OPENROUTER_API_KEY: ${OPENROUTER_API_KEY:-}` line from `odoo` service `environment:` block; update adjacent comment to say the key is configured via Settings UI | MEDIUM | Hygiene — key is managed in Settings, not env |
| `docs/plans/2026-05-25-tx10-ai-discuss-IMPLEMENTED.md` | Add a "Known Issues at deploy / Post-merge fixes" section referencing the 3 post-merge bugs and this task | LOW | Keep history continuous; no rewrite needed |

---

## Documents to Create

| Document | Content | Location | Priority |
|----------|---------|----------|---------|
| Implementation log | Routes/files added, patterns, deviations, verification evidence, commit list, PR link | `docs/plans/2026-05-25-fix-tx10ai-postmerge-IMPLEMENTED.md` | HIGH (required by CLAUDE.md post-task policy) |
| Bot info controller | Inline docstring in `bot_info.py` covering route, auth, response shape (no separate doc file needed) | `custom_addons/tx10_ai/controllers/bot_info.py` (new file) | HIGH |
| Systray component | `/** @odoo-module */` JSDoc header + inline comments in `tx10_ai_systray.js` | `custom_addons/tx10_ai/static/src/systray/tx10_ai_systray.js` (new file) | HIGH |
| Ukrainian i18n strings | uk.po entries for all `_ERROR_USER_MESSAGES` values (no_api_key, network_error, http_error, empty_choices, terminated_content_filter, terminated_length, unknown) | `custom_addons/tx10_ai/i18n/uk.po` (new file — directory does not exist yet) | MEDIUM |
| Error strings reference | Table of all `_ERROR_USER_MESSAGES` keys → Ukrainian text → English gloss; to be embedded in the implementation log, not a separate file | Section in `docs/plans/2026-05-25-fix-tx10ai-postmerge-IMPLEMENTED.md` | MEDIUM |

---

## Module Manifest Description Update

File: `custom_addons/tx10_ai/__manifest__.py`

**Only `"name"` changes.** All other fields stay as-is.

```
"name": "TX10 AI"        →   "name": "TeamX10 AI"
```

The `"summary"` field (`"TeamX10 AI assistant as a native Discuss bot"`) is already correct — no change needed.
The technical module id `tx10_ai`, model names `tx10.ai.*`, and xml_ids all stay unchanged.

---

## API Documentation — New Endpoint

### `POST /tx10_ai/bot_partner`

```
Method:  POST (JSON-RPC 2.0 convention, type='json')
Auth:    auth="user"  (requires active Odoo session)
Module:  custom_addons/tx10_ai/controllers/bot_info.py

Request body:  {} (no parameters)

Response:
  {
    "partner_id": <int>   # res.partner id of the tx10_ai bot (partner_ai_bot)
  }

Errors (standard Odoo JSON-RPC error envelope):
  - 403 if session is unauthenticated (handled by Odoo auth decorator)

Purpose:
  Returns the bot partner id so the systray OWL component can call
  mail.store.openChat({ partnerId }) to open/reopen the DM channel.
  Decoupled from ir.http.session_info to avoid polluting the global
  session payload for all users.

Consumers:
  - tx10_ai_systray.js onWillStart() — fetches once per page load
```

---

## Ukrainian i18n Strings (uk.po seed content)

These strings must appear in `custom_addons/tx10_ai/i18n/uk.po`.
They correspond to the `_ERROR_USER_MESSAGES` dict in `tx10_ai_chat.py`.

| error_code | Ukrainian text |
|------------|----------------|
| `no_api_key` | `🔌 AI-асистента ще не налаштовано. Зверніться до адміністратора.` |
| `network_error` | `⚠️ Сервіс AI тимчасово недоступний. Спробуйте пізніше.` |
| `http_error` | `⚠️ Сервіс AI тимчасово недоступний. Спробуйте пізніше.` |
| `empty_choices` | `🤔 Не вдалося згенерувати відповідь. Спробуйте перефразувати запит.` |
| `terminated_content_filter` | `🤔 Не вдалося згенерувати відповідь. Спробуйте перефразувати запит.` |
| `terminated_length` | `✂️ Відповідь завелика, будь ласка, звузьте запит.` |
| `unknown` | `❌ Виникла непередбачена помилка. Спробуйте ще раз або зверніться до адміністратора.` |

Admin-only code suffix appended by `_format_error()` (not a translatable string):
`\n\n— код: {error_code}`

---

## No-Update List

The following items explicitly do NOT need documentation changes and why:

| Item | Reason |
|------|--------|
| `docs/ARCHITECTURE.md` | Does not mention `custom_addons/` or specific modules; no drift |
| `docs/CODEMAP.md` | Module listing does not include custom addons by name |
| `docs/CONTEXT.md` | Describes research context / Odoo framework; no tx10_ai/solar_ai specifics |
| `docs/TECHSTACK.md` | Stack (Python, Odoo, PostgreSQL) unchanged by this task |
| `docs/PATTERNS/` (all 11 files) | Pattern files are framework-level; no tx10_ai-specific patterns |
| `docs/testing/solar-ai-chat-test-cases.md` | Historical test-case document for the old solar_ai module; becomes an archive artefact once solar_ai is deleted — leave as-is, no update or deletion |
| `CLAUDE.md` (project root) | No references to solar_ai or TX10 AI naming found; no change needed |
| `AGENTS.md` | No AI module references |
| `agents/` directory (IMPLEMENTATION.md, MEMORY.md) | No solar_ai or tx10_ai content |
| `.pm/knowledge/decisions.md` | Task-specific decisions tracked in task directory, not here |
| Historical plan docs (`docs/plans/2026-05-23-solar-ai-*`, `2026-05-24-solar-ai-*`) | Frozen historical artefacts; accuracy reflects the state at time of writing |
| `docs/plans/2026-05-25-tx10-ai-discuss.md` | Source plan doc — frozen at approval; do not modify plans after implementation |
| `custom_addons/solar_ai/` (entire directory) | Will be deleted via `git rm -r`; no documentation update required |
| `custom_addons/tx10_ai/tests/*.py` | Test files are code, not documentation; inline comments handled during impl |
| `CONTRIBUTING.md`, `SECURITY.md`, `README.md` (project root) | Odoo upstream files; tx10_ai is a custom addon, not mentioned here |

---

## Implementation Log Requirements

File to create: `docs/plans/2026-05-25-fix-tx10ai-postmerge-IMPLEMENTED.md`

Must include per CLAUDE.md post-task policy:

```
Sections:
  1. Goal — 3 post-merge bugs fixed (bot silent, solar_ai systray, silent errors)
  2. Routes/files added
     - controllers/bot_info.py  (/tx10_ai/bot_partner)
     - static/src/systray/tx10_ai_systray.{js,xml}
     - i18n/uk.po
  3. Files modified
     - models/tx10_ai_service.py  (error_code on all error returns)
     - models/tx10_ai_chat.py     (_ERROR_USER_MESSAGES, _format_error, anti-silence guarantee)
     - __manifest__.py            (name rename, systray assets, bot_info controller)
     - views/res_config_settings_views.xml  (block title rename)
     - custom_addons/solar_demo/__manifest__.py  (drop solar_ai dep)
     - docker-compose.yml         (remove OPENROUTER_API_KEY env)
  4. Files deleted
     - custom_addons/solar_ai/   (entire directory via git rm)
  5. Key patterns established
     - _ERROR_USER_MESSAGES dict + _format_error() — error surfacing pattern
     - bot_partner endpoint — minimal decoupled partner lookup
     - mail.store.openChat({partnerId}) — idempotent DM opener from systray
  6. Deviations from plan (if any)
  7. Verification evidence (test run output, grep results, manual boot check)
  8. Commits
  9. PR link
```
