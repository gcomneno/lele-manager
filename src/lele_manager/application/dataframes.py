"""Pandas conversion at the application/ML boundary."""

from __future__ import annotations

from collections.abc import Sequence
from io import StringIO
import json

import pandas as pd

from lele_manager.core.projection_store import LessonRecord


def records_to_legacy_dataframe(records: Sequence[LessonRecord]) -> pd.DataFrame:
    """Match the DataFrame inference historically produced by ``read_json``.

    Round-tripping the already validated records through Pandas' JSON reader is
    intentional: its date conversion, null representation, mixed-type and
    leading-zero handling are externally observable by the API and ML callers.
    Pandas remains outside the projection-store contract.
    """
    if not records:
        return pd.DataFrame()
    payload = "".join(
        json.dumps(record, ensure_ascii=False, default=str) + "\n" for record in records
    )
    return pd.read_json(StringIO(payload), lines=True)
