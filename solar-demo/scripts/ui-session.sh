#!/usr/bin/env bash
# ui-session.sh <tech|pm|svcmgr|admin> [destroy] — временная веб-сессия демо-пользователя для UI-проверок.
# Пароль берётся из .secrets и не выводится; cookie → .private/<роль>.cookies (каталог 700).
set -euo pipefail
D="$(cd "$(dirname "$0")/.." && pwd)"; R="$1"; J="$D/.private/$R.cookies"
set -a; source "$D/.secrets"; set +a
if [ "${2:-}" = destroy ]; then
  curl -s -b "$J" -H 'Content-Type: application/json' -d '{"jsonrpc":"2.0","params":{}}' \
    http://localhost:8069/web/session/destroy >/dev/null; rm -f "$J"; echo "session $R destroyed"; exit 0
fi
PWV="PW_$R"; LOGIN="demo-$R"; [ "$R" = admin ] && LOGIN=admin
python3 - "$LOGIN" "${!PWV}" > "$D/.private/req.json" <<'PY'
import json, sys
print(json.dumps({"jsonrpc": "2.0", "params": {"db": "solar_epc_demo19", "login": sys.argv[1], "password": sys.argv[2]}}))
PY
curl -s -c "$J" -H 'Content-Type: application/json' -d @"$D/.private/req.json" \
  http://localhost:8069/web/session/authenticate | python3 -c "import sys,json; r=json.load(sys.stdin); res=r.get('result') or {}; print('login', '$LOGIN', 'uid', res.get('uid'), 'is_admin', res.get('is_admin'), 'error', (r.get('error') or {}).get('message'))"
rm -f "$D/.private/req.json"; chmod 600 "$J"
