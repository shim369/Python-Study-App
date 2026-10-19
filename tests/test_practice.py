from core.models import CaseOutcome, GradeResult
from core.practice import PracticeState

PASSED = GradeResult(passed=True, cases=[CaseOutcome("t", True)])
FAILED = GradeResult(passed=False, cases=[CaseOutcome("t", False, "NG")])


def test_hints_are_revealed_one_by_one_up_to_total() -> None:
    state = PracticeState(total_hints=3)
    for _ in range(5):
        state.show_next_hint()
    assert state.hints_shown == 3
    assert not state.has_more_hints


def test_solution_is_hidden_until_passed() -> None:
    state = PracticeState(total_hints=3)
    state.record(FAILED)
    assert not state.can_view_solution
    state.record(PASSED)
    assert state.can_view_solution


def test_solution_can_be_revealed_explicitly() -> None:
    state = PracticeState(total_hints=3)
    state.reveal_solution()
    assert state.can_view_solution
    assert not state.passed


def test_record_counts_attempts_and_keeps_passed() -> None:
    state = PracticeState(total_hints=3)
    state.record(PASSED)
    state.record(FAILED)
    assert state.attempts == 2
    assert state.passed  # 一度合格したら合格のまま
    assert state.last_result is FAILED
