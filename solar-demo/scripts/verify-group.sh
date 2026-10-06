#!/usr/bin/env bash
# verify-group.sh <группа> <mod1,mod2,...> — состояние модулей, предупреждения лога, HTTP-проверка
set -uo pipefail
D="$(cd "$(dirname "$0")/.." && pwd)"; ROOT="$(cd "$D/.." && pwd)"
G="$1"; MODS="$2"; Q=$(echo "$MODS" | sed "s/[^,]*/'&'/g")
export PGPASSWORD="${DB_PASSWORD:-odoo}"; PSQL="psql -h 127.0.0.1 -U odoo -d solar_epc_demo19 -Atc"
echo "— состояние модулей группы $G:"; $PSQL "select name||' = '||state from ir_module_module where name in ($Q) order by name"
echo "— не в installed (вся БД): $($PSQL "select coalesce(string_agg(name||':'||state,', '),'нет') from ir_module_module where state in ('to install','to upgrade','to remove')")"
echo "— WARNING в логе: $(grep -c ' WARNING ' "$D/logs/install-$G.log")"; grep ' WARNING ' "$D/logs/install-$G.log" | sed -E 's/^.{0,24}//' | cut -c1-220 | sort | uniq -c | head -15
"$D/scripts/start.sh" >/dev/null || { echo "✗ старт не удался"; exit 1; }
for u in /web/login /odoo /web/webclient/version_info; do
  if [ "$u" = /web/webclient/version_info ]; then c=$(curl -s -o /dev/null -w '%{http_code}' -H 'Content-Type: application/json' -d '{}' http://localhost:8069$u)
  else c=$(curl -s -o /dev/null -w '%{http_code}' http://localhost:8069$u); fi; echo "  HTTP $c $u"; done
grep -cE "Traceback|ERROR" "$ROOT/.odoo-data/odoo19.log" | sed 's/^/— ERROR в серверном логе: /'
"$D/scripts/stop.sh" >/dev/null
