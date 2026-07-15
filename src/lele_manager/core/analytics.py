from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List, Literal

import pandas as pd

GroupBy = Literal["year", "month", "topic"]


def _iter_tags(df: pd.DataFrame) -> List[str]:
    tags: List[str] = []
    if "tags" not in df.columns:
        return tags
    for raw in df["tags"]:
        if isinstance(raw, list):
            tags.extend(str(t).strip() for t in raw if str(t).strip())
    return tags


def _date_series(df: pd.DataFrame) -> pd.Series:
    if "date" not in df.columns:
        return pd.Series([pd.NaT] * len(df), index=df.index)
    return pd.to_datetime(df["date"], errors="coerce", utc=True)


def compute_stats_summary(df: pd.DataFrame) -> Dict[str, Any]:
    """Aggregate lesson statistics for dashboard / CLI."""
    if df.empty:
        return {
            "n_lessons": 0,
            "n_topics": 0,
            "n_unique_tags": 0,
            "avg_text_length": 0.0,
            "avg_importance": None,
            "top_tags": [],
            "by_topic": [],
        }

    topics = df["topic"].dropna().astype(str).str.strip() if "topic" in df.columns else pd.Series(dtype=str)
    topics = topics[topics != ""]

    text_lengths = df["text"].fillna("").astype(str).str.len() if "text" in df.columns else pd.Series([0])
    all_tags = _iter_tags(df)
    tag_counts = Counter(all_tags)

    importance = None
    if "importance" in df.columns:
        imp = pd.to_numeric(df["importance"], errors="coerce").dropna()
        if not imp.empty:
            importance = float(imp.mean())

    by_topic_counts = topics.value_counts() if not topics.empty else pd.Series(dtype=int)
    topic_rows = [
        {"topic": str(topic), "count": int(count)}
        for topic, count in by_topic_counts.items()
    ]

    return {
        "n_lessons": int(len(df)),
        "n_topics": int(topics.nunique()) if not topics.empty else 0,
        "n_unique_tags": int(len(tag_counts)),
        "avg_text_length": round(float(text_lengths.mean()), 1),
        "avg_importance": round(importance, 2) if importance is not None else None,
        "top_tags": [{"tag": k, "count": v} for k, v in tag_counts.most_common(15)],
        "by_topic": topic_rows,
    }


def compute_timeline(df: pd.DataFrame, group_by: GroupBy = "month") -> Dict[str, Any]:
    """Bucket lessons by year, month, or topic for timeline views."""
    if df.empty:
        return {"group_by": group_by, "buckets": []}

    work = df.copy()
    if "id" not in work.columns:
        work["id"] = work.index.astype(str)

    buckets: Dict[str, List[str]] = {}

    if group_by == "topic":
        if "topic" not in work.columns:
            return {"group_by": group_by, "buckets": []}
        for _, row in work.iterrows():
            key = str(row.get("topic") or "(senza topic)")
            buckets.setdefault(key, []).append(str(row["id"]))
    else:
        dates = _date_series(work)
        lesson_ids = work["id"].astype(str).tolist()
        for lesson_id, dt in zip(lesson_ids, dates.tolist()):
            if pd.isna(dt):
                key = "(senza data)"
            elif group_by == "year":
                key = f"{dt.year:04d}"
            else:
                key = f"{dt.year:04d}-{dt.month:02d}"
            buckets.setdefault(key, []).append(lesson_id)

    bucket_list: List[Dict[str, Any]] = [
        {"key": key, "count": len(ids), "lesson_ids": ids}
        for key, ids in buckets.items()
    ]

    if group_by in ("year", "month"):
        bucket_list.sort(key=lambda b: (b["key"] == "(senza data)", b["key"]))
    else:
        bucket_list.sort(key=lambda b: (-b["count"], b["key"]))

    return {"group_by": group_by, "buckets": bucket_list}
