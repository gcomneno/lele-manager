#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PYTHON_BIN="$ROOT/.venv/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Missing required virtualenv Python: $PYTHON_BIN" >&2
  exit 1
fi

# Build every time so the server exposes the current frontend sources.
./scripts/build-gui.sh

"$PYTHON_BIN" scripts/e2e-prepare.py

export LELE_DATA_DIR="$ROOT/.e2e-fixture/data"
export LELE_CACHE_DIR="$ROOT/.e2e-fixture/cache"
export LELE_VAULT_DIR="$ROOT/.e2e-fixture/vault"

unset LELE_DATA_PATH
unset LELE_MODEL_PATH

exec "$PYTHON_BIN" -m uvicorn lele_manager.api.server:app \
  --host 127.0.0.1 \
  --port "${E2E_PORT:-8765}"
