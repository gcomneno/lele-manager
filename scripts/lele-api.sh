#!/usr/bin/env bash
set -euo pipefail

# Determina la root del progetto (cartella che contiene pyproject.toml)
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Attiva la venv se esiste
if [[ -d ".venv" ]]; then
  # shellcheck source=/dev/null
  source .venv/bin/activate
else
  echo "[errore] .venv non trovata in ${PROJECT_ROOT}."
  echo "Crea l'ambiente con: python -m venv .venv && source .venv/bin/activate && pip install -e .[dev]"
  exit 1
fi

echo "[info] Avvio LeLe API (dev) su http://127.0.0.1:8000 ..."
exec uvicorn lele_manager.api.server:app \
  --reload \
  --host 127.0.0.1 \
  --port 8000
