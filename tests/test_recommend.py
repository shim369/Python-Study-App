from datetime import UTC, date, datetime

from core.models import Exercise, IOCase
from core.progress import ExerciseProgress
from core.recommend import (
    TopicWeakness,
    recommend,
    struggle_score,
    weak_topics,
)
from core.srs import ReviewState

TODAY = date(2026, 10, 20)
T0 = datetime(2026, 10, 1, tzinfo=UTC)


def make_exercise(exercise_id: str, topic: str) -> Exercise:
    return Exercise(
        id=exercise_id,
        title=exercise_id,
        level=int(exercise_id[1]),
        topic=topic,
        description="d",
        starter_code="",
        grading="io",
        cases=[IOCase(expected_stdout="x")],
        hints=["a", "b", "c"],
        solution="print('x')",
    )


def progress(
    exercise_id: str,
    *,
    attempts: int = 1,
    failures: int = 0,
    hints: int = 0,
    solution_viewed: bool = False,
    passed: bool = False,
) -> ExerciseProgress:
    return ExerciseProgress(
        exercise_id,
        started_at=T0,
        attempts=attempts,
        failures=failures,
        hints_used=hints,
        solution_viewed=solution_viewed,
        first_passed_at=T0 if passed else None,
    )


def test_struggle_score() -> None:
    assert struggle_score(progress("l1-001-a", passed=True)) == 0
    assert struggle_score(progress("l1-001-a", failures=2, hints=1)) == 3
    assert struggle_score(progress("l1-001-a", solution_viewed=True)) == 3


def test_weak_topics_average_over_tried_exercises() -> None:
    exercises = [
        make_exercise("l1-001-a", "dict"),
        make_exercise("l1-002-b", "dict"),
        make_exercise("l1-003-c", "dict"),  # 未着手は平均に入れない
        make_exercise("l1-004-d", "loop"),
        make_exercise("l1-005-e", "string"),
    ]
    data = {
        "l1-001-a": progress("l1-001-a", failures=5, hints=3),  # 8
        "l1-002-b": progress("l1-002-b", passed=True),  # 0
        "l1-004-d": progress("l1-004-d", failures=1, hints=2, solution_viewed=True),  # 6
        "l1-005-e": progress("l1-005-e", failures=1),  # 1(苦手ではない)
        "l1-003-c": progress("l1-003-c", attempts=0),  # 開いただけ
    }
    assert weak_topics(exercises, data) == [
        TopicWeakness("loop", 6.0, 1),
        TopicWeakness("dict", 4.0, 2),
    ]


def test_recommend_priority_order() -> None:
    exercises = [
        make_exercise("l2-001-new", "generator"),
        make_exercise("l1-005-weak-new", "dict"),
        make_exercise("l1-004-trying", "loop"),
        make_exercise("l1-003-due-late", "string"),
        make_exercise("l1-002-due-early", "string"),
        make_exercise("l1-001-weak-tried", "dict"),
        make_exercise("l1-006-not-due", "set"),
    ]
    data = {
        "l1-004-trying": progress("l1-004-trying", failures=1),
        "l1-003-due-late": progress("l1-003-due-late", passed=True),
        "l1-002-due-early": progress("l1-002-due-early", passed=True),
        "l1-001-weak-tried": progress("l1-001-weak-tried", failures=4, passed=True),
        "l1-006-not-due": progress("l1-006-not-due", passed=True),
    }
    reviews = {
        "l1-003-due-late": ReviewState(1, date(2026, 10, 19)),
        "l1-002-due-early": ReviewState(0, date(2026, 10, 10)),
        "l1-006-not-due": ReviewState(0, date(2026, 10, 21)),
        "l1-001-weak-tried": ReviewState(3, None),
    }

    result = recommend(exercises, data, reviews, TODAY, limit=10)
    assert [(r.exercise.id, r.reason) for r in result] == [
        ("l1-002-due-early", "🔁 復習(1回目)"),
        ("l1-003-due-late", "🔁 復習(2回目)"),
        ("l1-004-trying", "✏️ 挑戦中"),
        ("l1-005-weak-new", "💪 苦手トピック「dict」"),
        ("l2-001-new", "🆕 次の問題"),
    ]


def test_recommend_limit_and_fresh_start() -> None:
    exercises = [make_exercise(f"l1-00{n}-x", "t") for n in range(1, 6)]
    result = recommend(exercises, {}, {}, TODAY, limit=2)
    assert [r.exercise.id for r in result] == ["l1-001-x", "l1-002-x"]
