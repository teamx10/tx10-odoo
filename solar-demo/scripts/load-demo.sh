#!/usr/bin/env bash
# Загрузка демоданных: load-demo.sh [шаг ...]  (по умолчанию все loader/[0-9]*.py по порядку)
# Выполняется через ORM в `odoo-bin shell`; commit — только если шаг прошёл без исключения.
set -euo pipefail
D="$(cd "$(dirname "$0")/.." && pwd)"; ROOT="$(cd "$D/.." && pwd)"
set -a; source "$D/.secrets"; set +a
STEPS=("$@"); [ ${#STEPS[@]} -eq 0 ] && STEPS=($(cd "$D/loader" && ls [0-9]*.py))
for s in "${STEPS[@]}"; do
  echo "══ $s"
  { cat "$D/loader/_lib.py"; echo; cat "$D/loader/$s"; echo; echo "env.cr.commit(); print('COMMIT OK $s')"; } |
    "$ROOT/.venv19/bin/python" "$ROOT/odoo-bin" shell -c "$ROOT/odoo19.conf" -d solar_epc_demo19 \
      --no-http --log-level=warn 2>&1 | grep -v '^>>>' | tee "$D/logs/step.out"
  cat "$D/logs/step.out" >> "$D/logs/load-demo.log"
  grep -q "COMMIT OK $s" "$D/logs/step.out" || { echo "✗ шаг $s не завершён"; exit 1; }
done
