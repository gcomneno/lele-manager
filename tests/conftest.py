# tests/conftest.py
import sys

from pathlib import Path

# Aggiunge la cartella "src" alla sys.path quando girano i test,
# così `import lele_manager` funziona anche senza install editable.
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
