#!/usr/bin/env bash
# backup.sh — дамп БД solar_epc_demo19 + filestore → solar-demo/backups/solar_epc_demo19-<дата>/
set -euo pipefail
D="$(cd "$(dirname "$0")/.." && pwd)"; ROOT="$(cd "$D/.." && pwd)"; PG=/opt/homebrew/opt/postgresql@17/bin
DB=solar_epc_demo19; B="$D/backups/$DB-$(date +%Y%m%d-%H%M%S)"; mkdir -p "$B"
PGPASSWORD="${DB_PASSWORD:-odoo}" "$PG/pg_dump" -h 127.0.0.1 -U odoo -Fc -f "$B/$DB.dump" "$DB"
tar -C "$ROOT/.odoo-data/filestore" -czf "$B/filestore-$DB.tgz" "$DB"
cp "$D/config/repos.lock" "$B/"
"$PG/pg_restore" -l "$B/$DB.dump" >/dev/null && tar -tzf "$B/filestore-$DB.tgz" >/dev/null
echo "✓ $B ($(du -sh "$B" | cut -f1))"
