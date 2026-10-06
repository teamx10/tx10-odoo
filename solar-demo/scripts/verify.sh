#!/usr/bin/env bash
# Проверка сценариев: verify.sh [файл ...] (по умолчанию все verify/s*.py). Результат → docs/results-latest.txt
set -euo pipefail; export SOLAR_DEMO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
D="$(cd "$(dirname "$0")/.." && pwd)"; ROOT="$(cd "$D/.." && pwd)"
FILES=("$@"); [ ${#FILES[@]} -eq 0 ] && FILES=($(cd "$D/verify" && ls s*.py))
mkdir -p "$D/docs"
{ cat "$D/loader/_lib.py" "$D/verify/_check.py"; for f in "${FILES[@]}"; do echo; cat "$D/verify/$f"; done
  echo; echo "summary(); env.cr.commit()"; } |
  "$ROOT/.venv19/bin/python" "$ROOT/odoo-bin" shell -c "$ROOT/odoo19.conf" -d solar_epc_demo19 \
    --no-http --log-level=warn 2>&1 | grep -v '^>>>' | tee "$D/logs/verify.out"
awk '/^(PASS|FAIL) \|/{f=1} f' "$D/logs/verify.out" > "$D/docs/results-latest.txt"
