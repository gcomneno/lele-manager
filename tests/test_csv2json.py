from pathlib import Path
from lele_manager.cli.csv2json import convert_csv_to_json

def test_convert_csv_to_json(tmp_path: Path) -> None:
    # prepara un CSV di prova
    csv_path = tmp_path / "input.csv"
    json_path = tmp_path / "output.json"

    csv_content = "id,text\n1,hello\n2,world\n"
    csv_path.write_text(csv_content, encoding="utf-8")

    # esegue la conversione
    count = convert_csv_to_json(csv_path, json_path)

    assert count == 2
    assert json_path.exists()
    data = json_path.read_text(encoding="utf-8")
    assert '"id": "1"' in data
    assert '"text": "hello"' in data
