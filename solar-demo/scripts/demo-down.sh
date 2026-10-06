#!/usr/bin/env bash
# Закрыть публичное демо: :8443 обратно только в tailnet (KTD2), затем стоп Odoo.
# Не `funnel … off`: оно удаляет обработчик порта целиком.
set -uo pipefail
source "$(dirname "$0")/_funnel-lib.sh"

"$TS" serve --bg --https=$FUNNEL_PORT "http://127.0.0.1:$PORT" 2>&1 | grep -v '^Warning: client version'
if funnel_public || ! serve_has_port; then
  echo "✗ :$FUNNEL_PORT всё ещё публичен или пропал из serve"; print_funnel_state; exit 1
fi
echo "✓ :$FUNNEL_PORT только в tailnet"
"$(dirname "$0")/stop.sh"
print_funnel_state
