#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON_BIN="$ROOT/.venv/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="python"
fi
if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  PYTHON_BIN="python3"
fi

# Build every time so the E2E server serves the current frontend sources.
./scripts/build-gui.sh

"$PYTHON_BIN" scripts/e2e-prepare.py

export LELE_DATA_PATH="$ROOT/.e2e-fixture/lessons.jsonl"
export LELE_MODEL_PATH="$ROOT/.e2e-fixture/topic_model.joblib"
export LELE_VAULT_DIR="$ROOT/.e2e-fixture/vault"

exec "$PYTHON_BIN" -m uvicorn lele_manager.api.server:app --host 127.0.0.1 --port "${E2E_PORT:-8765}"
