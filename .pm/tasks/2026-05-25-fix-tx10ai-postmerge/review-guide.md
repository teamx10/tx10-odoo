# Review Guide: Fix tx10_ai post-merge issues

**Task ID:** 2026-05-25-fix-tx10ai-postmerge
**Status:** flow-pending
**Created:** 2026-05-25

---

## What to Review

This task fixes three post-deploy bugs in `tx10_ai`:

| # | Bug | Fix |
|---|-----|-----|
| 1 | Bot never replies (API key not mapped) | Anti-silence guarantee + error code surfacing |
| 2 | Old solar_ai navbar still showing | Remove solar_ai, add new tx10_ai systray |
| 3 | All errors silently swallowed | Friendly message always posted |

---

## Key Decisions (locked)

| Decision | Value |
|----------|-------|
| Error code visibility | `base.group_system` only |
| solar_ai removal strategy | Shell-uninstall (primary) |
| Error message i18n | `_()` / `_lt()` Odoo wrappers |
| Systray icon | `fa fa-comments` (FA4.7, no `fa-robot`) |
| Bot partner | `tx10_ai.partner_ai_bot` (has `active=False`, needs `sudo()`) |

---

## Security Checklist (pre-merge)

- [ ] `solar_ai.*` config params deleted from `ir.config_parameter` (T09b)
- [ ] Non-admin users cannot see `— код:` suffix in bot messages
- [ ] `_format_error` uses `Markup.escape(_(...))`, NOT `Markup(_(...))` (XSS prevention)
- [ ] `/tx10_ai/bot_partner` endpoint is `type="json"` (CSRF protected)
- [ ] `sudo()` only on `partner_ai_bot` browse and `message_post`

---

## Test Coverage Required

- `TestTx10AiErrorSurfacing` (4 test methods) must pass
- All existing `tx10_ai` tests must still pass
- Manual: navbar, floating chat, Settings block, bot replies

---

## Spec Documents

| Doc | Path |
|-----|------|
| spec.md | `.pm/tasks/2026-05-25-fix-tx10ai-postmerge/spec/spec.md` |
| architecture.md | `.pm/tasks/.../spec/architecture.md` |
| technical.md | `.pm/tasks/.../spec/technical.md` |
| security.md | `.pm/tasks/.../spec/security.md` |
| test-plan.md | `.pm/tasks/.../spec/test-plan.md` |
| docs-plan.md | `.pm/tasks/.../spec/docs-plan.md` |
| tasks.md | `.pm/tasks/.../spec/tasks.md` |
