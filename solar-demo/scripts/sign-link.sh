#!/usr/bin/env bash
# sign-link.sh — локально печатает портальные ссылки неподписанных запросов sign_oca
# (в реальности ссылка уходит письмом; на стенде почта заблокирована). Ссылку не публикуйте.
set -euo pipefail
D="$(cd "$(dirname "$0")/.." && pwd)"; ROOT="$(cd "$D/.." && pwd)"
echo "for s in env['sign.oca.request.signer'].sudo().search([('signed_on','=',False),('request_id.state','=','0_sent')]): print('LINK', s.request_id.name, '|', s.partner_id.name, '| http://localhost:8069' + s.access_url)" |
  "$ROOT/.venv19/bin/python" "$ROOT/odoo-bin" shell -c "$ROOT/odoo19.conf" -d solar_epc_demo19 --no-http --log-level=warn 2>&1 |
  grep '^LINK' | sed 's/^LINK //' || echo "нет неподписанных запросов"
