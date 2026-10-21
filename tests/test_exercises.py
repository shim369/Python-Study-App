"""全教材の自己検証(CI用): 模範解答が合格し、初期コードが不合格になること。"""

import ast

import pytest

from core.loader import load_all
from core.models import Exercise
from core.verify import verify_exercise

LOADED = load_all()


def test_all_exercises_load_without_errors() -> None:
    assert LOADED.errors == []
    assert LOADED.exercises, "教材が1問もありません"


@pytest.mark.parametrize("exercise", LOADED.exercises, ids=lambda ex: ex.id)
def test_has_english_translation(exercise: Exercise) -> None:
    """画面を English にしたときに日本語のまま残らないよう、全問に英訳(en:)を求める。"""
    assert exercise.en is not None


def code_without_docstrings(source: str) -> str:
    """コメントと docstring を除いたコードの構造(コメントは ast に残らない)。"""
    tree = ast.parse(source)
    docstring_owners = ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef
    for node in ast.walk(tree):
        if isinstance(node, docstring_owners) and ast.get_docstring(node) is not None:
            node.body = node.body[1:] or [ast.Pass()]
    return ast.dump(tree)


@pytest.mark.parametrize("exercise", LOADED.exercises, ids=lambda ex: ex.id)
def test_english_starter_differs_only_in_comments(exercise: Exercise) -> None:
    """英語版の初期コードは、コメントと docstring 以外は日本語版と同じであること。"""
    if exercise.en is None or exercise.en.starter_code is None:
        pytest.skip("英語版の初期コードなし")
    assert code_without_docstrings(exercise.en.starter_code) == code_without_docstrings(
        exercise.starter_code
    )


@pytest.mark.parametrize("exercise", LOADED.exercises, ids=lambda ex: ex.id)
def test_solution_passes_and_starter_fails(exercise: Exercise) -> None:
    report = verify_exercise(exercise)
    assert report.ok, report.problems
