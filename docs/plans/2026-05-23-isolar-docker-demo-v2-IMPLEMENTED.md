# IMPLEMENTED: iSolar Docker Demo v2

**Plan:** `docs/plans/2026-05-23-isolar-docker-demo-v2.md`
**Branch:** `feat/isolar-solar-project`
**Date:** 2026-05-23 → 2026-05-24
**Commit range:** `e404c37` → (final commit of this task)

---

## Goal

Add `solar_demo` Odoo module + Docker Compose so anyone runs `docker compose up` and gets Odoo 19 with iSolar branding, sample clients/projects/documents — zero manual steps.

---

## Files Added / Modified

```
custom_addons/solar_demo/
  __init__.py                      — thin module init (no Python models)
  __manifest__.py                  — depends: [solar_project, solar_ai], data: [], demo: [...]
  tests/__init__.py                — explicit import (Odoo doesn't auto-discover tests)
  tests/test_solar_demo.py         — 12 tests: branding (4) + data (6) + constraints (2)
  demo/branding.xml                — noupdate=1: company name/colors + partner logo
  demo/solar_demo_data.xml         — 3 partners, 3 projects, 3 tasks, 6 docs, 6 checklist items
  data/img/isolar_logo.png         — 256×256 RGBA PNG (green circle, amber rays, "iSolar" text)

docker/
  Dockerfile                       — FROM odoo:19 + pip install httpx
  odoo.conf                        — list_db=False, dbfilter=isolar, addons_path=/mnt/extra-addons
  README.md                        — quick-start guide

docker-compose.yml                 — db (postgres:17) + odoo (custom build), healthchecks, volumes
.env.example                       — DB_PASSWORD + OPENROUTER_API_KEY placeholders
.gitignore                         — !.env.example exclusion added
```

---

## Key Design Decisions

### `demo/` vs `data/`
All branding and sample records live in `demo/` — zero production side-effects. Installing
`solar_demo` on a production DB (without `--with-demo`) loads nothing at all.

### `noupdate="1"` in branding.xml
Demo data loads with `noupdate=True` automatically (Odoo `loading.py`), but the explicit
`<data noupdate="1">` wrapper documents intent: branding is set-once; `-u solar_demo` never
reverts operator customisations.

### Odoo 19 `new_db_demo=False`
Unlike Odoo ≤18, demo data is off by default. `--with-demo` is required in the compose command
and in any test invocation that touches demo records.

### `addons_path = /mnt/extra-addons` only
`initialize_sys_path()` in `odoo/modules/module.py` always prepends the core addon dirs
regardless of `addons_path`. Adding explicit core paths would duplicate them and risk ordering
issues — verified against Odoo 19 source.

### `list_db = False` replaces `admin_passwd`
DB manager is disabled via `list_db=False` + `dbfilter=isolar`. No master password needed
(or exposed on the command line / `docker inspect`).

### Python/urllib healthcheck
The official `odoo:19` image does not guarantee `curl`. Replaced with a one-liner that uses
`python3` (always present) + `urllib.request`.

---

## IT-Team Review (2026-05-23)

Run: `.it-team/run-2026-05-23-18-09/REVIEW.md`

| Finding | Severity | Action |
|---|---|---|
| admin_passwd in cmdline | BLOCKER | **Fixed** — removed, `list_db=False` makes it moot |
| addons_path missing core | BLOCKER | **Rejected** — `initialize_sys_path()` adds core dirs automatically |
| branding without noupdate | MAJOR | **Partially applied** — added explicit `<data noupdate="1">` for documentation clarity |
| skip guard missing in tests | MAJOR | **Fixed** — `loaded_demo_data()` guard in setUp for demo-dependent classes |
| assertRaises too broad | MAJOR | **Fixed** — narrowed to `IntegrityError` + `@mute_logger` + `flush_all()` |
| solar_ai dependency | MAJOR | **Retained** — intentional demo bundle; AI menu must be visible in showcase |
| --break-system-packages | MAJOR | **Retained** — correct for system Python in official Odoo image |
| curl healthcheck | MAJOR | **Fixed** — replaced with python3/urllib one-liner |
| -i on every restart | MAJOR | **Retained** — no-op for already-installed modules; documented tradeoff |

---

## Test Results

```
# With --with-demo (12 tests)
solar_demo: 12 PASS, 0 fail, 0 error

# Without --with-demo (CI mode)
solar_demo: 10 SKIPPED, 2 PASS (constraint tests), 0 fail
```

---

## Smoke Test Results (2026-05-24)

```
docker compose up -d --build   → exit 0
db container                   → healthy (postgres:17)
odoo container                 → healthy (46s first boot)
GET /web/health                → HTTP 200
solar_demo loaded              → module 97/97, branding.xml + solar_demo_data.xml OK
Modules loaded.                → confirmed in logs
```

Manual UI checklist: **all items passed** (confirmed by user).

---

## Commits

```
e404c37  [ADD] solar_demo: scaffold module with empty data stubs and full test suite
ae2256f  [ADD] solar_demo: add placeholder iSolar logo (256×256 PNG)
de1c28b  [ADD] solar_demo: demo/branding.xml — iSolar Energy company name, logo, and colours
4f47c28  [ADD] solar_demo: demo partners (3 clients) and projects (survey/install/handover)
aee29d4  [ADD] solar_demo: demo tasks (3) and solar documents (6, varied types/states)
10267be  [ADD] solar_demo: demo checklist items (6 items across 2 tasks, mixed done/pending)
f60d897  [ADD] solar_demo: Docker Dockerfile (httpx pinned), odoo.conf (no secrets), .env.example
d16215f  [ADD] solar_demo: docker-compose.yml — self-seeding iSolar demo stack
2d3e56b  [FIX] solar_demo: address IT-team review findings
(final)  [FIX] solar_demo: add author key to manifest, docker/README.md
```
