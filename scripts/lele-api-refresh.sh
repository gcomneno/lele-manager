#!/usr/bin/env bash
set -euo pipefail

# Root del progetto (cartella che contiene pyproject.toml)
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

# Defaults: in dev usiamo percorsi repo-local (override con LELE_DATA_PATH/LELE_MODEL_PATH)
export LELE_DATA_PATH="${LELE_DATA_PATH:-data/lessons.jsonl}"
export LELE_MODEL_PATH="${LELE_MODEL_PATH:-models/topic_model.joblib}"


# Directory del vault LeLe (puoi sovrascriverla con la variabile LELE_VAULT_DIR)
VAULT_DIR="${LELE_VAULT_DIR:-$HOME/LeLeVault}"

echo "[info] Root progetto: ${PROJECT_ROOT}"
echo "[info] Vault LeLe:    ${VAULT_DIR}"

if [[ ! -d "${VAULT_DIR}" ]]; then
  echo "[errore] Vault directory non trovata: ${VAULT_DIR}"
  echo "Crea/aggiusta LELE_VAULT_DIR oppure la cartella ${VAULT_DIR}."
  exit 1
fi

# Attiva la venv se esiste
if [[ -d ".venv" ]]; then
  # shellcheck source=/dev/null
  source .venv/bin/activate
else
  echo "[errore] .venv non trovata in ${PROJECT_ROOT}."
  echo "Crea l'ambiente con:"
  echo "  python -m venv .venv"
  echo "  source .venv/bin/activate"
  echo "  pip install -e .[dev]"
  exit 1
fi

echo "[step 1/3] Importo LeLe dal vault -> data/lessons.jsonl ..."
python -m lele_manager.cli.import_from_dir \
  "${VAULT_DIR}" \
  data/lessons.jsonl \
  --on-duplicate overwrite \
  --default-source note \
  --default-importance 3 \
  --write-missing-frontmatter

echo "[step 2/3] Alleno topic model -> models/topic_model.joblib ..."
python -m lele_manager.cli.train_topic_model \
  --input data/lessons.jsonl \
  --output models/topic_model.joblib \
  --overwrite

echo "[step 3/3] Avvio LeLe API (dev) su http://127.0.0.1:8000 ..."
exec uvicorn lele_manager.api.server:app \
  --reload \
  --host 127.0.0.1 \
  --port 8000
