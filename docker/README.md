# iSolar Docker Demo

Zero-step demo environment for Odoo 19 with iSolar branding and sample data.

## Prerequisites

- Docker Desktop (or Docker Engine + Compose plugin)
- `git clone` of this repo

## Quick Start

```bash
# 1. Copy secrets template
cp .env.example .env        # edit DB_PASSWORD if desired

# 2. Start the stack (first boot ~3–5 min — installs all modules)
docker compose up -d --build

# 3. Open Odoo
open http://localhost:8069   # login: admin / admin
```

## What you get

| | |
|---|---|
| Company | iSolar Energy (green/amber branding) |
| Clients | Sonnenhaus GmbH · Green Valley Farm · Riverside Logistics |
| Projects | 3 solar projects across survey / installation / handover stages |
| Documents | 6 solar documents (approved / review / draft states) |
| Checklists | 6 checklist items (mixed done / pending) |
| AI features | Menu visible; inactive until `OPENROUTER_API_KEY` is set |

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `DB_PASSWORD` | *(required)* | PostgreSQL password for the `odoo` user |
| `OPENROUTER_API_KEY` | *(empty)* | Leave empty — AI features degrade gracefully |

## Useful commands

```bash
# Follow logs during first boot
docker compose logs -f odoo

# Stop stack (data preserved in volumes)
docker compose down

# Full reset — destroy volumes and start fresh
docker compose down -v && docker compose up -d --build
```

## Architecture notes

- **`odoo:19` official image** — entrypoint reads `HOST`/`USER`/`PASSWORD` env vars for DB
- **`odoo.conf`** — `list_db=False` + `dbfilter=isolar` pin the single demo DB; no DB manager exposed
- **`--with-demo`** — required by Odoo 19 (`new_db_demo=False` default); seeds iSolar branding + sample records on first boot only
- **`-i solar_demo`** — installs the module on first boot; no-op on subsequent restarts
