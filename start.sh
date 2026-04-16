#!/bin/bash
# Start Claude Editor
cd "$(dirname "$0")"
source venv/bin/activate 2>/dev/null || true
python3 app.py "$@"
