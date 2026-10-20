from datetime import UTC, datetime

from core.models import CaseOutcome, GradeResult
from core.practice import PracticeState
from core.progress import ExerciseProgress

PASSED = GradeResult(passed=True, cases=[CaseOutcome("t", True)])
FAILED = GradeResult(passed=False, cases=[CaseOutcome("t", False, "NG")])
T0 = datetime(2026, 10, 1, tzinfo=UTC)


def test_hints_are_revealed_one_by_one_up_to_total() -> None:
    state = PracticeState(total_hints=3)
    for _ in range(5):
        state.show_next_hint()
    assert state.hints_shown == 3
    assert not state.has_more_hints


def test_solution_is_hidden_until_passed() -> None:
    state = PracticeState(total_hints=3)
    state.record(FAILED, "ng")
    assert not state.can_view_solution
    state.record(PASSED, "ok")
    assert state.can_view_solution


def test_solution_can_be_revealed_explicitly() -> None:
    state = PracticeState(total_hints=3)
    state.reveal_solution()
    assert state.can_view_solution
    assert not state.passed


def test_record_counts_attempts_and_keeps_passed() -> None:
    state = PracticeState(total_hints=3)
    state.record(PASSED, "ok")
    state.record(FAILED, "ng")
    assert state.attempts == 2
    assert state.passed  # 一度合格したら合格のまま
    assert state.last_result is FAILED
    assert state.last_code == "ng"


def test_from_progress_without_saved_data_is_fresh() -> None:
    assert PracticeState.from_progress(3, None) == PracticeState(total_hints=3)


def test_from_progress_restores_saved_state() -> None:
    saved = ExerciseProgress(
        "l1-001-x",
        started_at=T0,
        attempts=4,
        hints_used=2,
        solution_viewed=True,
        first_passed_at=T0,
    )
    state = PracticeState.from_progress(3, saved)
    assert (state.attempts, state.hints_shown, state.passed) == (4, 2, True)
    assert state.solution_revealed
    assert state.last_result is None  # 採点結果の詳細は保存していない


def test_from_progress_caps_hints_when_exercise_has_fewer() -> None:
    saved = ExerciseProgress("l1-001-x", started_at=T0, hints_used=5)
    assert PracticeState.from_progress(3, saved).hints_shown == 3


def test_ai_hints_go_up_to_three_levels() -> None:
    state = PracticeState(total_hints=3)
    levels = []
    while state.next_ai_hint_level is not None:
        levels.append(state.next_ai_hint_level)
        state.use_ai_hint()
    state.use_ai_hint()  # 使い切った後は何も起きない
    assert levels == [1, 2, 3]
    assert state.ai_hints_used == 3


def test_ai_explain_and_review_depend_on_last_result() -> None:
    state = PracticeState(total_hints=3)
    assert not state.can_explain_failure
    assert not state.can_request_review
    state.record(FAILED, "ng")
    assert state.can_explain_failure
    assert not state.can_request_review
    state.record(PASSED, "ok")
    assert not state.can_explain_failure
    assert state.can_request_review
