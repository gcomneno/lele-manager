from __future__ import annotations

import httpx

def test_cli_suggest_basic(monkeypatch, capsys):
    from lele_manager.cli.lele import cmd_suggest  # adjust if your module path differs

    class Resp:
        status_code = 200
        def json(self):
            return {"query": "hello", "results": [{"id": "abc", "score": 0.9, "text_preview": "preview"}]}
        text = ""

    monkeypatch.setattr(httpx.Client, "post", lambda self, url, json: Resp())

    class Args:
        top_k = 5
        min_score = 0.1
        json = False
        text = "hello"
        file = None
        watch = None
        every = 2

    rc = cmd_suggest("http://test", Args())
    assert rc == 0
    out = capsys.readouterr().out
    assert "abc" in out
