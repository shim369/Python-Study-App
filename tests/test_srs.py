from datetime import date, datetime, time, timedelta

import pytest

from core.progress import AttemptRecord
from core.srs import ReviewState, review_state, review_states

DAY0 = date(2026, 10, 1)


def attempt(day_offset: int, passed: bool, exercise_id: str = "l1-001-x") -> AttemptRecord:
    """DAY0 から day_offset 日後の正午(ローカル時刻)の挑戦。"""
    at = datetime.combine(DAY0 + timedelta(days=day_offset), time(12)).astimezone()
    return AttemptRecord(exercise_id, at, passed, None, 10)


def state(*attempts: tuple[int, bool]) -> ReviewState | None:
    return review_state([attempt(day, passed) for day, passed in attempts])


def due_in(days: int) -> date:
    return DAY0 + timedelta(days=days)


def test_not_passed_yet_has_no_review() -> None:
    assert state() is None
    assert state((0, False), (0, False)) is None


def test_first_pass_schedules_review_after_one_day() -> None:
    assert state((0, False), (0, True)) == ReviewState(reviews_done=0, due_date=due_in(1))


def test_reviews_follow_1_3_7_days_then_complete() -> None:
    assert state((0, True), (1, True)) == ReviewState(1, due_in(1 + 3))
    assert state((0, True), (1, True), (4, True)) == ReviewState(2, due_in(4 + 7))
    done = state((0, True), (1, True), (4, True), (11, True))
    assert done == ReviewState(3, None)
    assert done is not None and done.completed


def test_late_review_counts_from_the_day_it_was_done() -> None:
    assert state((0, True), (5, True)) == ReviewState(1, due_in(5 + 3))


def test_attempts_before_due_date_are_ignored() -> None:
    assert state((0, True), (0, True), (0, False)) == ReviewState(0, due_in(1))
    assert state((0, True), (1, True), (2, True)) == ReviewState(1, due_in(4))


def test_failed_review_restarts_from_one_day_interval() -> None:
    lapsed = state((0, True), (1, True), (4, False))
    assert lapsed == ReviewState(1, due_in(4))  # まだ期限が来たまま(要復習)
    assert state((0, True), (1, True), (4, False), (4, True)) == ReviewState(0, due_in(5))


def test_attempts_after_completion_are_ignored() -> None:
    assert state((0, True), (1, True), (4, True), (11, True), (30, False)) == ReviewState(3, None)


@pytest.mark.parametrize(
    ("today_offset", "expected"),
    [(0, False), (1, True), (5, True)],
)
def test_is_due(today_offset: int, expected: bool) -> None:
    assert ReviewState(0, due_in(1)).is_due(due_in(today_offset)) is expected


def test_completed_review_is_never_due() -> None:
    assert not ReviewState(3, None).is_due(due_in(100))


def test_next_review_number() -> None:
    assert ReviewState(0, due_in(1)).next_review_number == 1


def test_review_states_only_include_passed_exercises() -> None:
    history = {
        "l1-001-a": [attempt(0, True, "l1-001-a")],
        "l1-002-b": [attempt(0, False, "l1-002-b")],
    }
    assert review_states(history) == {"l1-001-a": ReviewState(0, due_in(1))}
