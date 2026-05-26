#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_DIR"

"$REPO_DIR/docker-stop.sh"
"$REPO_DIR/docker-start.sh" -i tx10_ai
