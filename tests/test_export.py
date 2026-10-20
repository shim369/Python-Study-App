import csv
import io
import json
from datetime import UTC, date, datetime, timedelta

from core.export import UTF8_BOM, attempts_to_csv, progress_to_json
from core.models import Exercise, IOCase
from core.progress import AttemptRecord, ExerciseProgress
from core.srs import ReviewState

T0 = datetime(2026, 10, 1, 3, 0, tzinfo=UTC)
EXERCISE = Exercise(
    id="l1-001-a",
    title="問題A",
    level=1,
    topic="dict",
    description="d",
    starter_code="",
    grading="io",
    cases=[IOCase(expected_stdout="x")],
    hints=["a", "b", "c"],
    solution="print('x')",
)
HISTORY = {
    # 問題ごとにまとまっていても、出力は時刻順になること
    "l1-001-a": [
        AttemptRecord("l1-001-a", T0, False, "AssertionError", 120),
        AttemptRecord("l1-001-a", T0 + timedelta(minutes=10), True, None, 90),
    ],
    "l9-001-deleted": [AttemptRecord("l9-001-deleted", T0 + timedelta(minutes=5), True, None, 1)],
}


def test_csv_has_bom_header_and_rows_in_time_order() -> None:
    text = attempts_to_csv([EXERCISE], HISTORY)
    assert text.startswith(UTF8_BOM)  # Excel で文字化けしないように
    rows = list(csv.reader(io.StringIO(text.removeprefix(UTF8_BOM))))
    assert rows[0][:3] == ["日時", "問題ID", "問題"]
    assert [row[1] for row in rows[1:]] == ["l1-001-a", "l9-001-deleted", "l1-001-a"]
    assert rows[1][2:] == ["問題A", "dict", "不合格", "AssertionError", "120"]
    assert rows[2][2] == ""  # 削除された教材でも履歴は残す
    assert rows[1][0] == T0.astimezone().isoformat(timespec="seconds")  # ローカル時刻


def test_csv_without_attempts_has_only_header() -> None:
    lines = attempts_to_csv([EXERCISE], {}).removeprefix(UTF8_BOM).splitlines()
    assert len(lines) == 1


def test_json_contains_progress_and_attempts() -> None:
    progress = {
        "l1-001-a": ExerciseProgress(
            "l1-001-a", started_at=T0, attempts=2, failures=1, first_passed_at=T0
        )
    }
    reviews = {"l1-001-a": ReviewState(0, date(2026, 10, 2))}
    data = json.loads(progress_to_json([EXERCISE], progress, HISTORY, reviews, T0))

    assert data["exported_at"] == T0.astimezone().isoformat(timespec="seconds")
    row = data["exercises"][0]
    assert row["status"] == "PASSED"
    assert (row["attempts"], row["failures"]) == (2, 1)
    assert row["next_review"] == "2026-10-02"
    assert [a["duration_ms"] for a in data["attempts"]] == [120, 1, 90]


def test_json_for_untouched_exercise() -> None:
    data = json.loads(progress_to_json([EXERCISE], {}, {}, {}, T0))
    row = data["exercises"][0]
    assert row["status"] == "NOT_STARTED"
    assert row["started_at"] is None
    assert row["next_review"] is None
    assert data["attempts"] == []
    assert "問題A" in progress_to_json([EXERCISE], {}, {}, {}, T0)  # 日本語をエスケープしない
