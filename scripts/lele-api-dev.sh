#!/usr/bin/env bash
set -euo pipefail

# Trova la root del progetto (cartella che contiene questo script e sale di uno)
ROOT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"

cd "$ROOT_DIR"

echo "[info] Root progetto: $ROOT_DIR"

if [ ! -d ".venv" ]; then
  echo "[errore] Ambiente virtuale .venv non trovato nella root del progetto."
  echo "         Crea la venv con:"
  echo "             python -m venv .venv"
  echo "             source .venv/bin/activate"
  echo "             pip install -e .[dev]"
  exit 1
fi

# Attiva la venv
# shellcheck disable=SC1091
source ".venv/bin/activate"

# Controllo rapido che uvicorn sia installato nella venv
if ! command -v uvicorn >/dev/null 2>&1; then
  echo "[errore] uvicorn non trovato nella venv."
  echo "         Installa i requirements (in venv) con:"
  echo "             pip install -e .[dev]"
  exit 1
fi

echo "[info] Avvio LeLe API (dev) su http://127.0.0.1:8000 ..."
echo "[info] Usa CTRL+C per fermare il server."

exec uvicorn lele_manager.api.server:app --reload
