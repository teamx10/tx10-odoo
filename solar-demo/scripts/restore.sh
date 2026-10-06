#!/usr/bin/env bash
# restore.sh <каталог_бэкапа> [имя_БД]  — восстановление в НОВУЮ БД (по умолчанию solar_epc_demo19_restored).
# Существующую БД не удаляет: чтобы заменить рабочую, остановите стенд, переименуйте БД вручную.
set -euo pipefail
D="$(cd "$(dirname "$0")/.." && pwd)"; ROOT="$(cd "$D/.." && pwd)"; PG=/opt/homebrew/opt/postgresql@17/bin
B="$1"; DB="${2:-solar_epc_demo19_restored}"; export PGPASSWORD="${DB_PASSWORD:-odoo}"
DUMP=$(ls "$B"/*.dump | head -1); FS=$(ls "$B"/filestore-*.tgz | head -1); SRC=$(basename "$FS" .tgz); SRC=${SRC#filestore-}
if "$PG/psql" -h 127.0.0.1 -U odoo -d postgres -Atc "select 1 from pg_database where datname='$DB'" | grep -q 1; then
  echo "✗ БД $DB уже существует — укажите другое имя"; exit 1; fi
[ -e "$ROOT/.odoo-data/filestore/$DB" ] && { echo "✗ filestore/$DB уже существует"; exit 1; }
"$PG/createdb" -h 127.0.0.1 -U odoo "$DB"
"$PG/pg_restore" -h 127.0.0.1 -U odoo -d "$DB" --no-owner "$DUMP"
T=$(mktemp -d); tar -C "$T" -xzf "$FS"; mv "$T/$SRC" "$ROOT/.odoo-data/filestore/$DB"; rmdir "$T"
echo "✓ восстановлено в $DB (filestore: .odoo-data/filestore/$DB)"
echo "  Для запуска на этой БД: db_name/dbfilter в odoo19.conf → $DB"
