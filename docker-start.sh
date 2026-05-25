#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_DIR"

UPDATE_MODULE=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        -u)
            UPDATE_MODULE="${2:-}"
            shift 2
            ;;
        *)
            echo "Unknown option: $1" >&2
            exit 1
            ;;
    esac
done

if [[ -n "$UPDATE_MODULE" ]]; then
    echo "Updating module: $UPDATE_MODULE ..."
    docker compose stop odoo
    docker compose run --rm odoo odoo -d isolar -u "$UPDATE_MODULE" --stop-after-init
    docker compose up -d odoo
    echo ""
    echo "Module '$UPDATE_MODULE' updated."
    echo "  URL:   http://localhost:8069"
    echo "  Login: admin / admin"
    exit 0
fi

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
