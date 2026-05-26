# Tasks: Fix tx10_ai post-merge issues

**Date:** 2026-05-25
**Branch:** `feat/tx10-ai-discuss`
**Size:** M
**Module:** `tx10_ai`, `solar_demo`

---

## Execution Order

### Phase 1: Pre-flight
- [ ] **T01** — Impact analysis (`gitnexus_impact`) on `_do_agent_cycle` and `_run_agent` — MUST run before any edits
- [ ] **T02** — Pre-check `solar_demo/` and `demo/` dirs for `solar_ai` XML references (grep)

### Phase 2: Part A — Error surfacing _(start after T01)_
- [ ] **T03** — `tx10_ai_service.py`: add `error_code` field to all error return payloads (~0.5h)
- [ ] **T04** — `tx10_ai_chat.py`: add `_ERROR_USER_MESSAGES` dict, `_format_error()` helper, anti-silence guarantee in message dispatch (~1h)
- [ ] **T05** — `tx10_ai/i18n/uk.po`: add Ukrainian strings for all new user-facing error messages (~0.25h)
- [ ] **T06** — `tests/test_tx10_ai_discuss.py`: add `TestTx10AiErrorSurfacing` test class covering all error paths (~1h)
- [ ] **T07** — Run test suite: `./odoo-bin -d isolar --test-tags tx10_ai --stop-after-init` — verify all pass (~0.25h)

### Phase 3: Part B — solar_ai removal _(can run in parallel with Phase 2 after T02)_
- [ ] **T08** — `solar_demo/__manifest__.py`: remove `solar_ai` from `depends` list (~0.1h)
- [ ] **T09** — [MANUAL] Shell-uninstall `solar_ai` from running `isolar` DB via `docker exec` (~0.25h)
  - Requires running container; execute: `docker exec -it <container> ./odoo-bin -d isolar -u solar_demo --stop-after-init` then drop module via shell or Odoo UI
- [ ] **T09b** — [MANUAL] Delete orphan `solar_ai.*` config params from DB (~0.1h)
  - `./odoo-bin shell -d isolar` → `env['ir.config_parameter'].sudo().search([('key', 'like', 'solar_ai.%')]).unlink(); env.cr.commit()`
  - Security: prevents plaintext API key from lingering in `ir.config_parameter` after module removal
- [ ] **T10** — `git rm -r custom_addons/solar_ai/` — hard-delete the module from repo (~0.1h)
- [ ] **T11** — `./docker-restart.sh` — confirm clean startup, no import errors (~0.1h)

### Phase 4: New systray + branding _(start after T11)_
- [ ] **T12** — `tx10_ai/controllers/bot_info.py`: new JSON-RPC endpoint returning bot metadata (~0.5h)
- [ ] **T13** — `tx10_ai/static/src/systray/tx10_ai_systray.js`: OWL systray component (robot icon in navbar) (~1h)
- [ ] **T14** — `tx10_ai/static/src/systray/tx10_ai_systray.xml`: OWL template for systray item (~0.25h)
- [ ] **T15** — `tx10_ai/__manifest__.py`: update module name + register systray assets in `web.assets_backend` bundle (~0.25h)
- [ ] **T16** — `tx10_ai/views/res_config_settings_views.xml`: update Settings block title for branding consistency (~0.1h)
- [ ] **T17** — `docker-compose.yml`: remove stale `OPENROUTER_API_KEY` env var (~0.1h)

### Phase 5: Verification
- [ ] **T18** — Grep check: `grep -r "solar_ai" custom_addons/` must return zero results (~0.1h)
- [ ] **T19** — [MANUAL] Boot + UI verification: one robot icon in navbar, floating chat opens, Settings block shows correct title (~0.25h)
- [ ] **T20** — [MANUAL] Bot behaviour test (~0.25h):
  - Empty API key → friendly Ukrainian error message shown in chat
  - Real API key → answer returned correctly
  - Bad/invalid key → friendly error, not a silent fail or traceback
- [ ] **T21** — `gitnexus detect-changes` audit: confirm affected symbols match expected scope, no unexpected blast radius (~0.25h)
- [ ] **T22** — Implementation log: create `docs/plans/2026-05-25-fix-tx10ai-postmerge-IMPLEMENTED.md` (~0.25h)

---

## Parallel Opportunities

```
T01 ──► T03 ──► T04 ──► T05 ──► T06 ──► T07
         │                                    \
T02 ──► T08 ──► T09 ──► T10 ──► T11            ──► T18 ──► T19 ──► T20 ──► T21 ──► T22
                                   │
                                  T12 ──► T13 ──► T14 ──► T15 ──► T16 ──► T17
```

- Phase 2 and Phase 3 can run in parallel once T01 + T02 complete.
- Phase 4 depends on T11 (clean boot after solar_ai removal).
- Phase 5 depends on all of Phase 2, 3, and 4 complete.

---

## Manual Steps (cannot be automated)

| Task | Why manual | Pre-condition |
|------|-----------|---------------|
| T09 | Requires running DB container + Odoo module registry update | Docker stack up |
| T19 | Browser UI check — navbar, chat open, settings label | Docker stack up after T11 |
| T20 | Requires real/empty/bad API keys in Settings | T19 done, keys available |

---

## Estimated Effort

| Task | Est. |
|------|------|
| T01 | 0.25h |
| T02 | 0.1h |
| T03 | 0.5h |
| T04 | 1.0h |
| T05 | 0.25h |
| T06 | 1.0h |
| T07 | 0.25h |
| T08 | 0.1h |
| T09 | 0.25h |
| T10 | 0.1h |
| T11 | 0.1h |
| T12 | 0.5h |
| T13 | 1.0h |
| T14 | 0.25h |
| T15 | 0.25h |
| T16 | 0.1h |
| T17 | 0.1h |
| T18 | 0.1h |
| T19 | 0.25h |
| T20 | 0.25h |
| T21 | 0.25h |
| T22 | 0.25h |
| **Total** | **~7.2h** |

Size: **M** (1–2 dev days accounting for manual steps and test iteration)

---

## Files Touched (summary)

| File | Change |
|------|--------|
| `custom_addons/tx10_ai/tx10_ai_service.py` | Add `error_code` to error returns |
| `custom_addons/tx10_ai/tx10_ai_chat.py` | Error messages dict, formatter, anti-silence |
| `custom_addons/tx10_ai/i18n/uk.po` | Ukrainian error strings |
| `custom_addons/tx10_ai/tests/test_tx10_ai_discuss.py` | `TestTx10AiErrorSurfacing` class |
| `custom_addons/tx10_ai/controllers/bot_info.py` | New file — bot metadata endpoint |
| `custom_addons/tx10_ai/static/src/systray/tx10_ai_systray.js` | New file — OWL systray |
| `custom_addons/tx10_ai/static/src/systray/tx10_ai_systray.xml` | New file — OWL template |
| `custom_addons/tx10_ai/__manifest__.py` | Name + asset registration |
| `custom_addons/tx10_ai/views/res_config_settings_views.xml` | Block title update |
| `custom_addons/solar_demo/__manifest__.py` | Remove solar_ai dependency |
| `custom_addons/solar_ai/` | DELETED (git rm -r) |
| `docker-compose.yml` | Remove OPENROUTER_API_KEY env |
