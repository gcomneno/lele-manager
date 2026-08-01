#!/usr/bin/env python3
"""Prepare isolated data, model, and vault fixtures for Playwright E2E tests."""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / ".e2e-fixture"
DATA_PATH = FIXTURE_DIR / "lessons.jsonl"
MODEL_PATH = FIXTURE_DIR / "topic_model.joblib"
VAULT_DIR = FIXTURE_DIR / "vault"

RECORDS = [
    {
        "id": "e2e/python-lesson",
        "text": "python pytest testing workflow and fixtures",
        "topic": "python",
        "source": "note",
        "importance": 4,
        "tags": ["python", "pytest"],
        "date": "2025-01-01",
        "title": "Pytest workflow",
        "created_at": "2025-01-01T10:00:00+00:00",
    },
    {
        "id": "e2e/git-lesson",
        "text": "git branching merge rebase strategies",
        "topic": "git",
        "source": "note",
        "importance": 3,
        "tags": ["git"],
        "date": "2025-02-01",
        "title": "Git branching",
        "created_at": "2025-02-01T10:00:00+00:00",
    },
    {
        "id": "e2e/git-lesson-copy",
        "text": "git branching merge rebase strategies",
        "topic": "git",
        "source": "note",
        "importance": 3,
        "tags": ["git"],
        "date": "2025-02-01",
        "title": "Git branching copy",
        "created_at": "2025-02-02T10:00:00+00:00",
    },
    {
        "id": "e2e/linux-lesson",
        "text": "linux networking iptables basics",
        "topic": "linux",
        "source": "note",
        "importance": 2,
        "tags": ["linux"],
        "date": "2025-03-01",
        "title": "Linux net",
        "created_at": "2025-03-01T10:00:00+00:00",
    },
]


def prepare_vault() -> None:
    """Reset only the dedicated E2E vault to a known healthy state."""
    shutil.rmtree(VAULT_DIR, ignore_errors=True)
    topic_dir = VAULT_DIR / "python"
    topic_dir.mkdir(parents=True)
    (topic_dir / "2025-01-01.e2e.md").write_text(
        """---
id: python/2025-01-01.e2e
topic: python
source: note
importance: 3
tags:
  - python
date: '2025-01-01'
title: E2E fixture
---
Healthy E2E vault lesson.
""",
        encoding="utf-8",
    )


def main() -> int:
    sys.path.insert(0, str(ROOT / "src"))
    from lele_manager.ml.features import TextFeatureConfig
    from lele_manager.ml.topic_model import TopicModelConfig, save_topic_model, train_topic_model

    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    prepare_vault()
    with DATA_PATH.open("w", encoding="utf-8") as f:
        for rec in RECORDS:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    df = pd.read_json(DATA_PATH, lines=True)
    cfg = TopicModelConfig(text_features=TextFeatureConfig(min_df=1))
    pipeline = train_topic_model(df, config=cfg)
    save_topic_model(pipeline, MODEL_PATH)
    print(
        f"E2E fixture ready: {DATA_PATH} ({len(RECORDS)} lessons), {MODEL_PATH}, {VAULT_DIR}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
