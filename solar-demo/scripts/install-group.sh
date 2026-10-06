#!/usr/bin/env bash
# Установка группы модулей: install-group.sh <имя_группы> <mod1,mod2,...>
# Лог группы: solar-demo/logs/install-<группа>.log; выход !=0 при traceback/ERROR.
set -uo pipefail
D="$(cd "$(dirname "$0")/.." && pwd)"; ROOT="$(cd "$D/.." && pwd)"
G="$1"; MODS="$2"; LOG="$D/logs/install-$G.log"; mkdir -p "$D/logs"; : > "$LOG"
"$ROOT/.venv19/bin/python" "$ROOT/odoo-bin" -c "$ROOT/odoo19.conf" -d solar_epc_demo19 \
  -i "$MODS" --stop-after-init --logfile "$LOG"
RC=$?
ERR=$(grep -cE "Traceback|ERROR|CRITICAL" "$LOG")
echo "rc=$RC errors=$ERR log=$LOG"
grep -E "Traceback|ERROR|CRITICAL" "$LOG" | head -20
[ $RC -eq 0 ] && [ "$ERR" -eq 0 ]
