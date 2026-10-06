#!/usr/bin/env bash
# Поднять публичное демо: Odoo 19 → проверки (KTD1) → Funnel :8443 (KTD2).
set -uo pipefail
source "$(dirname "$0")/_funnel-lib.sh"

"$(dirname "$0")/start.sh" || { echo "✗ start.sh не удался — Funnel не включаю"; exit 1; }

# Проверка 1: на 8069 слушает ровно один процесс, и он запущен с odoo19.conf
pids="$(lsof -nP -tiTCP:$PORT -sTCP:LISTEN 2>/dev/null | sort -u)"
if [ "$(echo "$pids" | grep -c .)" != "1" ] || \
   ! ps -o command= -p "$pids" | grep -q -- "-c $ROOT/odoo19.conf"; then
  echo "✗ на :$PORT работает не Odoo 19 (odoo19.conf) — Funnel не включён"
  ps -o pid,command -p $pids 2>/dev/null; exit 1
fi
echo "✓ на :$PORT работает Odoo 19 (PID $pids)"

# Проверка 2: менеджер БД закрыт. Форма create в HTML есть всегда (скрытая модалка),
# поэтому смотрим на баннер и на отказ /web/database/list.
page="$(curl -s http://127.0.0.1:$PORT/web/database/manager)"
list="$(curl -s -X POST -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"call","params":{}}' http://127.0.0.1:$PORT/web/database/list)"
if ! grep -q "database manager has been disabled" <<<"$page" || ! grep -q "AccessDenied" <<<"$list"; then
  echo "✗ менеджер БД не закрыт (list_db) — Funnel не включён"; exit 1
fi
echo "✓ менеджер БД закрыт"

"$TS" funnel --bg --https=$FUNNEL_PORT "http://127.0.0.1:$PORT" 2>&1 | grep -v '^Warning: client version'
funnel_public || { echo "✗ Funnel не включился"; print_funnel_state; exit 1; }
echo "✓ ПУБЛИЧНО: $PUBLIC_URL"
print_funnel_state
echo "⚠ После показа выполните: solar-demo/scripts/demo-down.sh"
