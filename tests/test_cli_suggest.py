from __future__ import annotations

import argparse

import httpx


def test_cli_suggest_basic(monkeypatch, capsys):
    from lele_manager.cli.lele import cmd_suggest

    class Resp:
        status_code = 200

        def json(self):
            return {
                "query": "hello",
                "results": [{"id": "abc", "score": 0.9, "text_preview": "preview"}],
            }

        text = ""

    def _post(self, url, json):
        # Optional, ma utile per inchiodare contratto e non far passare test "per caso"
        assert url == "/similar"
        assert json["text"] == "hello"
        assert json["top_k"] == 5
        assert json["min_score"] == 0.1
        return Resp()

    monkeypatch.setattr(httpx.Client, "post", _post)

    args = argparse.Namespace(
        top_k=5,
        min_score=0.1,
        json=False,
        text="hello",
        file=None,
        watch=None,
        every=2,
    )

    rc = cmd_suggest("http://test", args)
    assert rc == 0

    out = capsys.readouterr().out
    assert "abc" in out
