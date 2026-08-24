from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

from lele_manager.api import server


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def test_search_q_is_hybrid_retrieval_not_body_substring_filter(
    tmp_path: Path,
    monkeypatch,
) -> None:
    data_path = tmp_path / "lessons.jsonl"
    model_path = tmp_path / "topic.joblib"
    model_path.write_bytes(b"test-model-seam")

    _write_jsonl(
        data_path,
        [
            {
                "id": "lexical",
                "text": "Use idempotency keys for payment retries.",
                "title": "Payment retries",
                "topic": "payments",
                "importance": 3,
            },
            {
                "id": "semantic",
                "text": "Repeated operations should be safe to execute again.",
                "title": "Safe operations",
                "topic": "distributed-systems",
                "importance": 3,
            },
        ],
    )

    monkeypatch.setattr(server, "DATA_PATH", data_path)
    monkeypatch.setattr(server, "MODEL_PATH", model_path)
    monkeypatch.setattr(
        server,
        "build_similarity_index",
        lambda _df, _context=None: SimpleNamespace(
            transformer=object()
        ),
    )

    def fake_similar_by_text(
        df,
        query_text,
        transformer,
        top_k=None,
        min_score=None,
        ranking=None,
        backend=None,
    ):
        del query_text, transformer, top_k, min_score, ranking, backend
        ids = set(df["id"].astype(str))
        results = []
        if "semantic" in ids:
            results.append(
                SimpleNamespace(
                    lesson_id="semantic",
                    score=0.95,
                )
            )
        if "lexical" in ids:
            results.append(
                SimpleNamespace(
                    lesson_id="lexical",
                    score=0.20,
                )
            )
        return results

    monkeypatch.setattr(
        server,
        "similar_by_text",
        fake_similar_by_text,
    )

    response = TestClient(server.app).post(
        "/lessons/search",
        json={"q": "idempotency", "limit": 20},
    )

    assert response.status_code == 200
    payload = response.json()

    assert [item["id"] for item in payload] == [
        "lexical",
        "semantic",
    ]
    assert "idempotency" not in payload[1]["text"].casefold()
    assert payload[0]["why"][0]["code"] == "exact-phrase-match"
    assert any(
        reason["code"] == "semantic-similarity"
        for reason in payload[1]["why"]
    )
    assert payload[0]["semantic_available"] is True


def test_missing_model_degrades_to_lexical_search(
    tmp_path: Path,
    monkeypatch,
) -> None:
    data_path = tmp_path / "lessons.jsonl"

    _write_jsonl(
        data_path,
        [
            {
                "id": "lexical",
                "text": "Use idempotency keys.",
            },
            {
                "id": "unrelated",
                "text": "Git branching strategy.",
            },
        ],
    )

    monkeypatch.setattr(server, "DATA_PATH", data_path)
    monkeypatch.setattr(server, "MODEL_PATH", None)

    response = TestClient(server.app).post(
        "/lessons/search",
        json={"q": "idempotency", "limit": 20},
    )

    assert response.status_code == 200
    payload = response.json()

    assert [item["id"] for item in payload] == ["lexical"]
    assert payload[0]["semantic_available"] is False
    assert all(
        reason["code"] != "semantic-similarity"
        for reason in payload[0]["why"]
    )


def test_exact_title_remains_ahead_of_semantic_only_result(
    tmp_path: Path,
    monkeypatch,
) -> None:
    data_path = tmp_path / "lessons.jsonl"
    model_path = tmp_path / "topic.joblib"
    model_path.write_bytes(b"test-model-seam")

    _write_jsonl(
        data_path,
        [
            {
                "id": "exact",
                "title": "Python retries",
                "text": "Direct guidance.",
            },
            {
                "id": "semantic",
                "title": "Resilient operations",
                "text": "Conceptually related material.",
            },
        ],
    )

    monkeypatch.setattr(server, "DATA_PATH", data_path)
    monkeypatch.setattr(server, "MODEL_PATH", model_path)
    monkeypatch.setattr(
        server,
        "build_similarity_index",
        lambda _df, _context=None: SimpleNamespace(
            transformer=object()
        ),
    )
    monkeypatch.setattr(
        server,
        "similar_by_text",
        lambda *args, **kwargs: [
            SimpleNamespace(
                lesson_id="semantic",
                score=1.0,
            ),
            SimpleNamespace(
                lesson_id="exact",
                score=0.01,
            ),
        ],
    )

    response = TestClient(server.app).post(
        "/lessons/search",
        json={"q": "python retries", "limit": 20},
    )

    assert response.status_code == 200
    payload = response.json()

    assert [item["id"] for item in payload] == [
        "exact",
        "semantic",
    ]
    assert payload[0]["why"][0]["code"] == "exact-title-match"


def test_filters_constrain_semantic_candidate_universe(
    tmp_path: Path,
    monkeypatch,
) -> None:
    data_path = tmp_path / "lessons.jsonl"
    model_path = tmp_path / "topic.joblib"
    model_path.write_bytes(b"test-model-seam")

    _write_jsonl(
        data_path,
        [
            {
                "id": "allowed",
                "text": "Safe repeated operations.",
                "topic": "python",
            },
            {
                "id": "wrong-topic",
                "text": "Safe repeated operations.",
                "topic": "git",
            },
            {
                "id": "archived",
                "text": "Safe repeated operations.",
                "topic": "python",
                "lifecycle": "archived",
            },
        ],
    )

    monkeypatch.setattr(server, "DATA_PATH", data_path)
    monkeypatch.setattr(server, "MODEL_PATH", model_path)
    monkeypatch.setattr(
        server,
        "build_similarity_index",
        lambda _df, _context=None: SimpleNamespace(
            transformer=object()
        ),
    )

    seen_ids: list[str] = []

    def fake_similar_by_text(df, *args, **kwargs):
        del args, kwargs
        seen_ids.extend(df["id"].astype(str).tolist())
        return [
            SimpleNamespace(
                lesson_id=lesson_id,
                score=0.9,
            )
            for lesson_id in df["id"].astype(str)
        ]

    monkeypatch.setattr(
        server,
        "similar_by_text",
        fake_similar_by_text,
    )

    response = TestClient(server.app).post(
        "/lessons/search",
        json={
            "q": "idempotency",
            "topic_in": ["python"],
            "limit": 20,
        },
    )

    assert response.status_code == 200
    assert seen_ids == ["allowed"]
    assert [item["id"] for item in response.json()] == [
        "allowed"
    ]


def test_no_query_preserves_browse_order(
    tmp_path: Path,
    monkeypatch,
) -> None:
    data_path = tmp_path / "lessons.jsonl"

    _write_jsonl(
        data_path,
        [
            {
                "id": "a",
                "text": "A",
                "importance": 5,
                "created_at": "2025-01-01T00:00:00+00:00",
            },
            {
                "id": "b",
                "text": "B",
                "importance": 5,
                "created_at": "2026-01-01T00:00:00+00:00",
            },
            {
                "id": "c",
                "text": "C",
                "importance": 4,
                "created_at": "2027-01-01T00:00:00+00:00",
            },
            {
                "id": "d",
                "text": "D",
                "importance": 5,
            },
        ],
    )

    monkeypatch.setattr(server, "DATA_PATH", data_path)
    monkeypatch.setattr(server, "MODEL_PATH", None)

    response = TestClient(server.app).post(
        "/lessons/search",
        json={"limit": 20},
    )

    assert response.status_code == 200
    payload = response.json()

    assert [item["id"] for item in payload] == [
        "b",
        "a",
        "d",
        "c",
    ]
    assert [item["rank"] for item in payload] == [1, 2, 3, 4]
    assert all(item["hybrid_score"] is None for item in payload)
    assert all(item["why"] == [] for item in payload)
    assert all(
        item["semantic_available"] is None
        for item in payload
    )


def test_export_reuses_hybrid_search_without_metadata_leak(
    tmp_path: Path,
    monkeypatch,
) -> None:
    data_path = tmp_path / "lessons.jsonl"

    _write_jsonl(
        data_path,
        [
            {
                "id": "exact",
                "title": "Python retries",
                "text": "Direct guidance.",
            },
            {
                "id": "other",
                "title": "Other",
                "text": "Unrelated.",
            },
        ],
    )

    monkeypatch.setattr(server, "DATA_PATH", data_path)
    monkeypatch.setattr(server, "MODEL_PATH", None)

    client = TestClient(server.app)

    search = client.post(
        "/lessons/search",
        json={"q": "python retries", "limit": 20},
    )
    assert search.status_code == 200
    assert [item["id"] for item in search.json()] == ["exact"]

    exported = client.post(
        "/export/search",
        params={"format": "json"},
        json={"q": "python retries", "limit": 20},
    )
    assert exported.status_code == 200

    markdown = exported.json()["markdown"]

    assert "Direct guidance." in markdown
    assert "hybrid_score" not in markdown
    assert "semantic_available" not in markdown
    assert "why:" not in markdown
