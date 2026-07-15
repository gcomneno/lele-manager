from io import StringIO
import json

import pandas as pd
import pandas.testing as pdt

from lele_manager.application.dataframes import records_to_legacy_dataframe


def test_records_to_dataframe_has_golden_read_json_parity() -> None:
    records = [
        {"id": "001", "text": "Perché Unicode ☕", "date": "2025-02-01",
         "created_at": "2025-02-01T10:11:12Z", "title": None, "importance": 3,
         "metadata": {"unknown": "kept"}, "mixed": 7},
        {"id": "abc", "text": "日本語", "date": None, "created_at": None,
         "title": "present", "importance": None,
         "metadata": {"future": [1, "due"]}, "mixed": "007"},
    ]
    payload = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in records)
    legacy = pd.read_json(StringIO(payload), lines=True)
    actual = records_to_legacy_dataframe(records)
    pdt.assert_frame_equal(actual, legacy)
    assert actual.loc[0, "id"] == "001"
