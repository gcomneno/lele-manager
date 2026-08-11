#!/usr/bin/env python3
"""Prepare isolated data, model, staging, and vault fixtures for Playwright."""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
FIXTURE_DIR = ROOT / ".e2e-fixture"
DATA_DIR = FIXTURE_DIR / "data"
CACHE_DIR = FIXTURE_DIR / "cache"
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


def reset_fixture() -> None:
    """Reset only the dedicated E2E root, never personal runtime paths."""
    if FIXTURE_DIR.is_symlink() or FIXTURE_DIR.is_file():
        FIXTURE_DIR.unlink()
    else:
        shutil.rmtree(FIXTURE_DIR, ignore_errors=True)

    DATA_DIR.mkdir(parents=True)
    CACHE_DIR.mkdir(parents=True)
    VAULT_DIR.mkdir(parents=True)


def prepare_vault() -> None:
    """Create canonical Markdown for every projected fixture record.

    A refresh must retain the same fixture dataset; keeping a separate global
    JSONL fixture would hide the very multi-Vault boundary exercised by E2E.
    """
    for record in RECORDS:
        lesson_id = record["id"]
        topic_dir = VAULT_DIR / str(record["topic"])
        topic_dir.mkdir(parents=True, exist_ok=True)
        tags = "\n".join(f"  - {tag}" for tag in record["tags"])
        (topic_dir / f"{lesson_id.replace('/', '--')}.md").write_text(
            "---\n"
            f"id: {lesson_id}\n"
            f"topic: {record['topic']}\n"
            f"source: {record['source']}\n"
            f"importance: {record['importance']}\n"
            f"tags:\n{tags}\n"
            f"date: '{record['date']}'\n"
            f"title: {record['title']}\n"
            "---\n"
            f"{record['text']}\n",
            encoding="utf-8",
        )


def main() -> int:
    sys.path.insert(0, str(ROOT / "src"))

    from lele_manager.ml.features import TextFeatureConfig
    from lele_manager.ml.topic_model import (
        TopicModelConfig,
        save_topic_model,
        train_topic_model,
    )

    reset_fixture()
    prepare_vault()

    # Create the fixture through the real registry bootstrap path, then use
    # its stable identity for every derived artifact.
    os.environ["LELE_DATA_DIR"] = str(DATA_DIR)
    os.environ["LELE_CACHE_DIR"] = str(CACHE_DIR)
    os.environ["LELE_VAULT_DIR"] = str(VAULT_DIR)
    from lele_manager.core.vault_registry import active_vault_context

    context = active_vault_context()

    context.projection_path.parent.mkdir(parents=True, exist_ok=True)
    with context.projection_path.open("w", encoding="utf-8") as stream:
        for record in RECORDS:
            stream.write(json.dumps(record, ensure_ascii=False) + "\n")

    dataframe = pd.read_json(context.projection_path, lines=True)
    config = TopicModelConfig(text_features=TextFeatureConfig(min_df=1))
    pipeline = train_topic_model(dataframe, config=config)
    context.topic_model_path.parent.mkdir(parents=True, exist_ok=True)
    save_topic_model(pipeline, context.topic_model_path)

    print(
        "E2E fixture ready: "
        f"data={DATA_DIR}, cache={CACHE_DIR}, vault={VAULT_DIR}, id={context.vault_id} "
        f"({len(RECORDS)} lessons)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
