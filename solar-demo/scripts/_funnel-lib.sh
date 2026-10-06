#!/usr/bin/env bash
# Общие функции demo-up/demo-down. Клиент из приложения совпадает по версии с tailscaled
# (brew-клиент печатает предупреждение о несовпадении версий).
ROOT="/Users/temich/dev/tx10/tx10-odoo"
PORT=8069
FUNNEL_PORT=8443
PUBLIC_URL="https://mac-madfish-m1.tail331ad2.ts.net:$FUNNEL_PORT/odoo"
TS=/Applications/Tailscale.app/Contents/MacOS/Tailscale
[ -x "$TS" ] || TS="$(command -v tailscale)"

# Публичен ли :8443 (строка заголовка порта содержит «Funnel on»)
funnel_public() { "$TS" funnel status 2>/dev/null | grep -q ":$FUNNEL_PORT (Funnel on)"; }
serve_has_port() { "$TS" serve status 2>/dev/null | grep -q ":$FUNNEL_PORT "; }
print_funnel_state() {
  echo "── tailscale funnel status ──"; "$TS" funnel status 2>&1 | grep -v '^Warning: client version'
}
