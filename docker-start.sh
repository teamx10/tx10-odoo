#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_DIR"

if docker compose ps --status running | grep -q "odoo"; then
    echo "iSolar demo already running at http://localhost:8069"
    exit 0
fi

docker compose up -d

echo "iSolar demo started"
echo "  URL:   http://localhost:8069"
echo "  Login: admin / admin"
echo ""
echo "First boot takes ~3–5 min. Follow logs: docker compose logs -f odoo"
