"""全教材の自己検証(CI用): 模範解答が合格し、初期コードが不合格になること。"""

import pytest

from core.loader import load_all
from core.models import Exercise
from core.verify import verify_exercise

LOADED = load_all()


def test_all_exercises_load_without_errors() -> None:
    assert LOADED.errors == []
    assert LOADED.exercises, "教材が1問もありません"


@pytest.mark.parametrize("exercise", LOADED.exercises, ids=lambda ex: ex.id)
def test_solution_passes_and_starter_fails(exercise: Exercise) -> None:
    report = verify_exercise(exercise)
    assert report.ok, report.problems
