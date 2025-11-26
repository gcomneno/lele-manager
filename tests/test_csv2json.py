import pytest

from pathlib import Path

from lele_manager.cli.csv2json import convert_csv_to_json

def test_convert_csv_to_json_missing_input(tmp_path: Path) -> None:
    input_path = tmp_path / "missing.csv"
    output_path = tmp_path / "out.json"

    with pytest.raises(FileNotFoundError):
        convert_csv_to_json(input_path, output_path)
