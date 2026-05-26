# Decisions — 2026-05-25-fix-tx10ai-postmerge

## Locked (from design review)

| # | Question | Decision |
|---|----------|----------|
| D1 | Navbar robot fate | New tx10_ai systray button → opens TeamX10 AI DM as floating chat window (`mail.store.openChat`). Normal icon (not `fa-android`). |
| D2 | API key source | UI Settings only. Remove `OPENROUTER_API_KEY` env from docker-compose. Settings block named "TeamX10 AI Assistant". |
| D3 | Error verbosity | Friendly localized message + short technical code for admin only. |

## Resolved in spec Q&A (2026-05-25)

| # | Question | Decision | Rationale |
|---|----------|----------|-----------|
| Q1 | Who sees `— код: X` error suffix? | `base.group_system` only | All users in this deploy may be project managers by default → showing codes to all PMs is meaningless; admins only is appropriate |
| Q2 | Primary path for solar_ai removal | Shell-uninstall (`odoo-bin shell` → `button_immediate_uninstall` → `git rm`) | Preserves isolar demo data; docker volume drop is fallback only |
| Q3 | Error message strings localization | Odoo `_()` / `_lt()` i18n wrappers | Correct Odoo convention; requires .po file entries in `tx10_ai/i18n/` |
