# tests/conftest.py
import sys

from pathlib import Path

import pytest

# Aggiunge la cartella "src" alla sys.path quando girano i test,
# così `import lele_manager` funziona anche senza install editable.
ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--optional-ai",
        action="store_true",
        help="Collect optional-AI contracts (requires installed GiadaWare AI).",
    )


def pytest_ignore_collect(collection_path: Path, config: pytest.Config) -> bool | None:
    # Exclude before importing modules, rather than skipping missing packages.
    if (
        collection_path == ROOT / "tests" / "optional_ai"
        and not config.getoption("--optional-ai")
    ):
        return True
    return None
