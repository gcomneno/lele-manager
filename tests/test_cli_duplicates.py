from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from lele_manager.cli import lele


REPORT = {
    "lessons_analyzed": 2,
    "total_pairs": 1,
    "exact_pairs": 0,
    "near_pairs": 1,
    "min_score": 0.85,
    "exact_only": False,
    "pairs": [{"left_id": "a", "right_id": "b", "left_position": 0, "right_position": 1, "kind": "near", "score": 0.91, "reasons": ["same_topic", "shared_tags"], "shared_tags": ["python"]}],
}

EXACT_REPORT = {
    **REPORT,
    "exact_pairs": 1,
    "near_pairs": 0,
    "exact_only": True,
    "pairs": [
        {
            "left_id": "same",
            "right_id": "same",
            "left_position": 0,
            "right_position": 1,
            "kind": "exact",
            "score": 1.0,
            "reasons": ["duplicate_id"],
            "shared_tags": [],
        }
    ],
}


class Response:
    def __init__(self, status_code: int = 200, data=REPORT) -> None:
        self.status_code = status_code
        self.data = data
        self.text = json.dumps(data)

    def json(self):
        return self.data


def install_client(monkeypatch, calls, response=Response()) -> None:
    class Client:
        def __init__(self, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

        def get(self, path, params=None):
            calls.append((path, params))
            return response

    monkeypatch.setattr(lele, "httpx", SimpleNamespace(Client=Client, RequestError=Exception))


def run(argv):
    with pytest.raises(SystemExit) as exc:
        lele.main(argv)
    return exc.value.code


def test_parameters(monkeypatch) -> None:
    calls = []
    install_client(monkeypatch, calls, Response(data=EXACT_REPORT))
    assert run(["duplicates", "--min-score", "0.8", "--limit", "10", "--exact-only"]) == 0
    assert calls == [("/duplicates", {"min_score": 0.8, "exact_only": True, "limit": 10})]


def test_human_output_uses_one_based_rows(monkeypatch, capsys) -> None:
    install_client(monkeypatch, [], Response(data=EXACT_REPORT))
    assert run(["duplicates", "--exact-only"]) == 0
    output = capsys.readouterr().out
    assert "[EXACT] same (riga 1) ↔ same (riga 2)" in output


def test_human_output_metadata(monkeypatch, capsys) -> None:
    install_client(monkeypatch, [])
    assert run(["duplicates"]) == 0
    output = capsys.readouterr().out
    assert "tag condivisi: python" in output


def test_json_has_no_extra_text(monkeypatch, capsys) -> None:
    install_client(monkeypatch, [])
    assert run(["duplicates", "--json"]) == 0
    captured = capsys.readouterr()
    assert json.loads(captured.out) == REPORT
    assert captured.err == ""


def test_no_candidates_message(monkeypatch, capsys) -> None:
    empty = {**REPORT, "total_pairs": 0, "near_pairs": 0, "pairs": []}
    install_client(monkeypatch, [], Response(data=empty))
    assert run(["duplicates"]) == 0
    assert "Nessun duplicato" in capsys.readouterr().out


def test_api_error_is_nonzero(monkeypatch, capsys) -> None:
    install_client(monkeypatch, [], Response(status_code=500, data={"detail": "boom"}))
    assert run(["duplicates"]) == 1
    assert "500" in capsys.readouterr().err


def test_model_unavailable_has_actionable_error(monkeypatch, capsys) -> None:
    install_client(monkeypatch, [], Response(status_code=503, data={"detail": "missing"}))
    assert run(["duplicates"]) == 1
    assert "--exact-only" in capsys.readouterr().err


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        (["--min-score", "nan"], "min-score"),
        (["--limit", "0"], "limit"),
        (["--limit", "10001"], "limit"),
    ],
)
def test_invalid_parameters_are_rejected_locally(monkeypatch, capsys, arguments, message) -> None:
    calls = []
    install_client(monkeypatch, calls)
    assert run(["duplicates", *arguments]) == 2
    assert message in capsys.readouterr().err
    assert calls == []
