from core.models import Exercise, ExerciseTranslation
from core.verify import verify_exercise

TESTS = "from solution import double\n\ndef test_double():\n    assert double(2) == 4\n"


def make_exercise(starter: str, solution: str) -> Exercise:
    return Exercise(
        id="l1-001-double",
        title="2倍",
        level=1,
        topic="function",
        description="2倍にする",
        starter_code=starter,
        grading="pytest",
        test_source=TESTS,
        hints=["a", "b", "c"],
        solution=solution,
        time_limit_sec=2,
    )


def test_good_exercise_is_ok() -> None:
    report = verify_exercise(make_exercise("def double(n): ...", "def double(n): return n * 2"))
    assert report.ok
    assert report.problems == []


def test_broken_solution_is_reported() -> None:
    report = verify_exercise(make_exercise("def double(n): ...", "def double(n): return n + 1"))
    assert not report.ok
    assert report.problems == ["模範解答が不合格: test_double"]


def test_starter_that_passes_is_reported() -> None:
    exercise = make_exercise("def double(n): return n * 2", "def double(n): return 2 * n")
    report = verify_exercise(exercise)
    assert report.problems == ["初期コードのままで合格してしまう(テストが弱い)"]


def test_english_starter_that_passes_is_reported() -> None:
    exercise = make_exercise("def double(n): ...", "def double(n): return n * 2")
    english = ExerciseTranslation(
        title="Double",
        description="Double it",
        hints=["a", "b", "c"],
        starter_code="def double(n): return n * 2  # Implement here",
    )
    report = verify_exercise(exercise.model_copy(update={"en": english}))
    assert report.problems == ["英語版の初期コードのままで合格してしまう(テストが弱い)"]
