from datetime import UTC, date, datetime, timedelta

import pytest

from core.dashboard import TopicMastery, format_duration, status_of, study_streak, topic_mastery
from core.models import Exercise, IOCase
from core.progress import ExerciseProgress, Status

TODAY = date(2026, 10, 20)
T0 = datetime(2026, 10, 1, tzinfo=UTC)


def days_ago(*offsets: int) -> set[date]:
    return {TODAY - timedelta(days=n) for n in offsets}


def make_exercise(exercise_id: str, level: int, topic: str) -> Exercise:
    return Exercise(
        id=exercise_id,
        title=exercise_id,
        level=level,
        topic=topic,
        description="d",
        starter_code="",
        grading="io",
        cases=[IOCase(expected_stdout="x")],
        hints=["a", "b", "c"],
        solution="print('x')",
    )


def passed(exercise_id: str) -> ExerciseProgress:
    return ExerciseProgress(exercise_id, started_at=T0, attempts=1, first_passed_at=T0)


@pytest.mark.parametrize(
    ("dates", "expected"),
    [
        (set(), 0),
        (days_ago(0), 1),
        (days_ago(0, 1, 2), 3),
        (days_ago(1, 2), 2),  # 今日はまだでも、昨日までの連続は途切れていない
        (days_ago(0, 2, 3), 1),  # 昨日が抜けたので今日の1日だけ
        (days_ago(2, 3), 0),  # 昨日も今日もやっていない
    ],
)
def test_study_streak(dates: set[date], expected: int) -> None:
    assert study_streak(dates, TODAY) == expected


def test_status_of_unknown_exercise_is_not_started() -> None:
    assert status_of("l1-001-x", {}) is Status.NOT_STARTED
    assert status_of("l1-001-x", {"l1-001-x": passed("l1-001-x")}) is Status.PASSED


def test_topic_mastery_counts_passed_per_topic_sorted_by_level() -> None:
    exercises = [
        make_exercise("l2-001-gen", 2, "generator"),
        make_exercise("l1-001-a", 1, "string"),
        make_exercise("l1-002-b", 1, "string"),
        make_exercise("l3-001-c", 3, "string"),  # 複数レベルにまたがるトピック
    ]
    progress = {"l1-001-a": passed("l1-001-a"), "l3-001-c": passed("l3-001-c")}

    assert topic_mastery(exercises, progress) == [
        TopicMastery(level=1, topic="string", passed=2, total=3),
        TopicMastery(level=2, topic="generator", passed=0, total=1),
    ]


def test_mastery_ratio() -> None:
    assert TopicMastery(1, "t", passed=1, total=4).ratio == 0.25
    assert TopicMastery(1, "t", passed=0, total=0).ratio == 0.0


@pytest.mark.parametrize(
    ("duration", "expected"),
    [
        (timedelta(seconds=0), "0秒"),
        (timedelta(seconds=45), "45秒"),
        (timedelta(minutes=12, seconds=30), "12分"),
        (timedelta(hours=3), "3時間"),
        (timedelta(hours=3, minutes=5), "3時間5分"),
        (timedelta(days=2), "2日"),
        (timedelta(days=2, hours=4, minutes=30), "2日4時間"),
    ],
)
def test_format_duration(duration: timedelta, expected: str) -> None:
    assert format_duration(duration) == expected


@pytest.mark.parametrize(
    ("duration", "expected"),
    [
        (timedelta(seconds=45), "45s"),
        (timedelta(hours=3, minutes=5), "3h 5m"),
        (timedelta(days=2, hours=4), "2d 4h"),
    ],
)
def test_format_duration_in_english(duration: timedelta, expected: str) -> None:
    assert format_duration(duration, "en") == expected
