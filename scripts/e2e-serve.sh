#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ -n "${E2E_PYTHON:-}" ]]; then
  PYTHON_BIN="$E2E_PYTHON"
elif [[ -x "$ROOT/.venv/bin/python" ]]; then
  PYTHON_BIN="$ROOT/.venv/bin/python"
else
  PYTHON_BIN="$(command -v python3 || command -v python || true)"
fi

if [[ -z "$PYTHON_BIN" || ! -x "$PYTHON_BIN" ]]; then
  echo "No usable Python interpreter found (set E2E_PYTHON, install python3, or create .venv)." >&2
  exit 1
fi

# Build every time so the server exposes the current frontend sources.
export LELE_SKIP_FRONTEND_INSTALL=1
./scripts/build-gui.sh

"$PYTHON_BIN" scripts/e2e-prepare.py

export LELE_DATA_DIR="$ROOT/.e2e-fixture/data"
export LELE_CACHE_DIR="$ROOT/.e2e-fixture/cache"
export LELE_VAULT_DIR="$ROOT/.e2e-fixture/vault"
# The shared validation virtualenv is editable from the main checkout.  Keep
# this worktree's source first so Playwright always exercises the code it just
# built, rather than a stale sibling checkout.
export PYTHONPATH="$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

unset LELE_DATA_PATH
unset LELE_MODEL_PATH

exec "$PYTHON_BIN" -m uvicorn lele_manager.api.server:app \
  --host 127.0.0.1 \
  --port "${E2E_PORT:-8765}"
