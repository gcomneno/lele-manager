#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON_BIN="python"
if ! command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python3"
fi

if [[ ! -f src/lele_manager/gui/static/index.html ]]; then
  ./scripts/build-gui.sh
fi

"$PYTHON_BIN" scripts/e2e-prepare.py

export LELE_DATA_PATH="$ROOT/.e2e-fixture/lessons.jsonl"
export LELE_MODEL_PATH="$ROOT/.e2e-fixture/topic_model.joblib"

exec "$PYTHON_BIN" -m uvicorn lele_manager.api.server:app --host 127.0.0.1 --port 8765
