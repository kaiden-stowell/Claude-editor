#!/bin/bash
cd "$(dirname "$0")"
[ -f .env ] && set -a && source .env && set +a
source venv/bin/activate 2>/dev/null || true
echo "Starting Claude Editor at http://127.0.0.1:${EDITOR_PORT:-12795}"
python3 app.py "$@"
