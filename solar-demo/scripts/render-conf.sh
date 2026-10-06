#!/usr/bin/env bash
# Собирает рабочий odoo19.conf из шаблона + solar-demo/.secrets (секреты не попадают в шаблон).
set -euo pipefail
D="$(cd "$(dirname "$0")/.." && pwd)"; ROOT="$(cd "$D/.." && pwd)"
source "$D/.secrets"
umask 077
sed -e "s|__MASTER_PASSWD__|$MASTER_PASSWD|" -e "s|__DB_PASSWORD__|${DB_PASSWORD:-odoo}|" \
  "$D/config/odoo19.conf.example" > "$ROOT/odoo19.conf"
chmod 600 "$ROOT/odoo19.conf"   # `>` не меняет права уже существующего файла
echo "✓ $ROOT/odoo19.conf собран"
