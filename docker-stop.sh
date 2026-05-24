#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_DIR"

# Pass --volumes (-v) to also wipe DB and start fresh next time:
#   ./docker-stop.sh --volumes
docker compose down "$@"

if [[ "${1:-}" == "--volumes" || "${1:-}" == "-v" ]]; then
    echo "iSolar demo stopped — DB volumes destroyed (next start = fresh demo)"
else
    echo "iSolar demo stopped — data preserved (restart: ./docker-start.sh)"
fi
