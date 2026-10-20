"""学習ログのエクスポート(CSV・JSON)。

- CSV: 挑戦1回ごとの履歴。Excel で開いても文字化けしないよう、先頭に BOM を付ける
- JSON: 問題ごとの進捗と全履歴。バックアップや、他のツールでの分析用
"""

import csv
import io
import json
from datetime import date, datetime
from typing import Any

from core.models import Exercise
from core.progress import AttemptRecord, ExerciseProgress
from core.srs import ReviewState

CSV_COLUMNS = ["日時", "問題ID", "問題", "トピック", "結果", "エラー種別", "実行時間(ms)"]
UTF8_BOM = "﻿"


def _local(moment: datetime | None) -> str | None:
    """保存は UTC なので、人が読むためにローカル時刻の ISO 形式に直す。"""
    return moment.astimezone().isoformat(timespec="seconds") if moment else None


def _all_attempts(history: dict[str, list[AttemptRecord]]) -> list[AttemptRecord]:
    """問題ごとに分かれた履歴を1列に並べ、古い順にする。"""
    flat = [attempt for records in history.values() for attempt in records]
    return sorted(flat, key=lambda attempt: attempt.attempted_at)


def attempts_to_csv(exercises: list[Exercise], history: dict[str, list[AttemptRecord]]) -> str:
    by_id = {ex.id: ex for ex in exercises}
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_COLUMNS)
    for attempt in _all_attempts(history):
        exercise = by_id.get(attempt.exercise_id)  # 教材が削除されていても履歴は出す
        writer.writerow(
            [
                _local(attempt.attempted_at),
                attempt.exercise_id,
                exercise.title if exercise else "",
                exercise.topic if exercise else "",
                "合格" if attempt.passed else "不合格",
                attempt.error_type or "",
                attempt.duration_ms,
            ]
        )
    return UTF8_BOM + buffer.getvalue()


def progress_to_json(
    exercises: list[Exercise],
    progress: dict[str, ExerciseProgress],
    history: dict[str, list[AttemptRecord]],
    reviews: dict[str, ReviewState],
    exported_at: datetime,
) -> str:
    def exercise_row(exercise: Exercise) -> dict[str, Any]:
        found = progress.get(exercise.id)
        review = reviews.get(exercise.id)
        next_review: date | None = review.due_date if review else None
        return {
            "id": exercise.id,
            "title": exercise.title,
            "level": exercise.level,
            "topic": exercise.topic,
            "status": found.status.name if found else "NOT_STARTED",
            "attempts": found.attempts if found else 0,
            "failures": found.failures if found else 0,
            "hints_used": found.hints_used if found else 0,
            "solution_viewed": found.solution_viewed if found else False,
            "started_at": _local(found.started_at) if found else None,
            "first_passed_at": _local(found.first_passed_at) if found else None,
            "next_review": next_review.isoformat() if next_review else None,
        }

    attempts = [
        {
            "exercise_id": attempt.exercise_id,
            "attempted_at": _local(attempt.attempted_at),
            "passed": attempt.passed,
            "error_type": attempt.error_type,
            "duration_ms": attempt.duration_ms,
        }
        for attempt in _all_attempts(history)
    ]
    data = {
        "exported_at": _local(exported_at),
        "exercises": [exercise_row(ex) for ex in exercises],
        "attempts": attempts,
    }
    return json.dumps(data, ensure_ascii=False, indent=2)
