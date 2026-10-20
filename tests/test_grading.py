import pytest

from core.grading import MAX_CODE_CHARS, detect_error_type, grade, normalize_output, run_free
from core.models import Exercise, IOCase


def make_pytest_exercise(**overrides: object) -> Exercise:
    data: dict[str, object] = {
        "id": "l1-001-double",
        "title": "2倍",
        "level": 1,
        "topic": "function",
        "description": "引数を2倍にする",
        "starter_code": "def double(n):\n    pass\n",
        "grading": "pytest",
        "test_source": (
            "from solution import double\n\ndef test_double():\n    assert double(2) == 4\n"
        ),
        "hints": ["h1", "h2", "h3"],
        "solution": "def double(n):\n    return n * 2\n",
        "time_limit_sec": 2,
    }
    data.update(overrides)
    return Exercise.model_validate(data)


def make_io_exercise() -> Exercise:
    return Exercise(
        id="l1-002-echo",
        title="大文字",
        level=1,
        topic="string",
        description="入力を大文字にして出力",
        starter_code="",
        grading="io",
        cases=[
            IOCase(stdin="abc\n", expected_stdout="ABC"),
            IOCase(stdin="x\n", expected_stdout="X\n"),
        ],
        hints=["h1", "h2", "h3"],
        solution="print(input().upper())\n",
        time_limit_sec=2,
    )


def test_pytest_solution_passes() -> None:
    ex = make_pytest_exercise()
    result = grade(ex, ex.solution)
    assert result.passed
    assert result.passed_count == 1
    assert result.error_type is None


def test_pytest_starter_fails_with_assertion() -> None:
    ex = make_pytest_exercise()
    result = grade(ex, ex.starter_code)
    assert not result.passed
    assert result.error_type == "AssertionError"


def test_pytest_timeout() -> None:
    ex = make_pytest_exercise(time_limit_sec=1)
    result = grade(ex, "while True:\n    pass\n")
    assert result.timed_out
    assert result.error_type == "Timeout"


def test_code_too_long() -> None:
    result = grade(make_pytest_exercise(), "#" * (MAX_CODE_CHARS + 1))
    assert not result.passed
    assert result.error_type == "CodeTooLong"


def test_io_solution_passes() -> None:
    ex = make_io_exercise()
    result = grade(ex, ex.solution)
    assert result.passed
    assert result.passed_count == 2


def test_io_wrong_answer() -> None:
    result = grade(make_io_exercise(), "print(input())\n")
    assert not result.passed
    assert result.error_type == "WrongAnswer"
    assert "期待" in result.cases[0].message


def test_io_runtime_error() -> None:
    result = grade(make_io_exercise(), "int('x')\n")
    assert not result.passed
    assert result.error_type == "ValueError"
    assert "ValueError" in result.cases[0].message


def test_io_timeout_stops_remaining_cases() -> None:
    ex = make_io_exercise().model_copy(update={"time_limit_sec": 1})
    result = grade(ex, "while True:\n    pass\n")
    assert result.timed_out
    assert len(result.cases) == 1


def test_exercise_requires_tests_for_pytest_grading() -> None:
    with pytest.raises(ValueError, match=r"test_solution\.py"):
        make_pytest_exercise(test_source=None)


def test_exercise_requires_three_hints() -> None:
    with pytest.raises(ValueError):
        make_pytest_exercise(hints=["only one"])


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Traceback...\nZeroDivisionError: division by zero", "ZeroDivisionError"),
        ("KeyError then ValueError: bad", "ValueError"),
        ("all good", None),
        # pytest の失敗詳細は最終行の "file:line: 種別" を優先する
        ("Failed: DID NOT RAISE <class 'ValueError'>\n\ntest_solution.py:9: Failed", "Failed"),
    ],
)
def test_detect_error_type(text: str, expected: str | None) -> None:
    assert detect_error_type(text) == expected


def test_normalize_output_ignores_trailing_whitespace() -> None:
    assert normalize_output("a  \nb\n\n") == normalize_output("a\nb")


def test_run_free_executes_code_with_stdin() -> None:
    result = run_free("print(input()[::-1])", "abc")
    assert result.ok
    assert result.stdout.strip() == "cba"


def test_run_free_rejects_too_long_code() -> None:
    with pytest.raises(ValueError, match="長すぎます"):
        run_free("#" * (MAX_CODE_CHARS + 1))
