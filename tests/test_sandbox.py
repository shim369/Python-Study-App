from pathlib import Path

import pytest

from runner.pytest_runner import parse_junit, run_pytest, run_script
from runner.sandbox import RunLimits, run_python

FAST = RunLimits(timeout_sec=2.0)


def test_normal_script_outputs_stdout() -> None:
    result = run_script("print('hello')", stdin="")
    assert result.ok
    assert result.stdout == "hello\n"
    assert not result.timed_out


def test_stdin_is_passed() -> None:
    result = run_script("print(input().upper())", stdin="abc\n")
    assert result.stdout == "ABC\n"


def test_exception_is_reported_not_raised() -> None:
    result = run_script("1 / 0", stdin="")
    assert result.returncode == 1
    assert "ZeroDivisionError" in result.stderr


def test_syntax_error() -> None:
    result = run_script("def f(:\n", stdin="")
    assert not result.ok
    assert "SyntaxError" in result.stderr


def test_infinite_loop_times_out() -> None:
    result = run_script("while True:\n    pass\n", stdin="", limits=RunLimits(timeout_sec=1.0))
    assert result.timed_out
    assert result.returncode is None
    assert not result.ok
    assert result.duration_ms < 4000


def test_sleeping_child_process_is_killed_with_group() -> None:
    code = (
        "import subprocess, sys\n"
        "subprocess.run([sys.executable, '-c', 'import time; time.sleep(30)'])\n"
    )
    result = run_script(code, stdin="", limits=RunLimits(timeout_sec=1.0))
    assert result.timed_out
    assert result.duration_ms < 4000


def test_huge_output_is_truncated() -> None:
    limits = RunLimits(timeout_sec=3.0, max_output_bytes=1000)
    result = run_script("while True:\n    print('x' * 1000)\n", stdin="", limits=limits)
    assert result.truncated
    assert len(result.stdout) <= 1000


def test_file_size_limit_is_enforced() -> None:
    limits = RunLimits(timeout_sec=3.0, max_file_bytes=10_000)
    code = "with open('big.bin', 'wb') as f:\n    f.write(b'0' * 100_000)\nprint('wrote')\n"
    result = run_script(code, stdin="", limits=limits)
    assert not result.ok
    assert "wrote" not in result.stdout


def test_environment_variables_do_not_leak(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "secret-key")
    result = run_script("import os\nprint(os.environ.get('ANTHROPIC_API_KEY'))", stdin="")
    assert result.stdout.strip() == "None"


def test_run_python_uses_workdir(tmp_path: Path) -> None:
    (tmp_path / "data.txt").write_text("42", encoding="utf-8")
    result = run_python(["-c", "print(open('data.txt').read())"], workdir=tmp_path, limits=FAST)
    assert result.stdout.strip() == "42"


TESTS = """
from solution import add

def test_add():
    assert add(1, 2) == 3

def test_add_negative():
    assert add(-1, -2) == -3
"""


def test_pytest_all_pass() -> None:
    result = run_pytest("def add(a, b):\n    return a + b\n", TESTS)
    assert result.passed
    assert [c.name for c in result.cases] == ["test_add", "test_add_negative"]


def test_pytest_partial_failure() -> None:
    result = run_pytest("def add(a, b):\n    return 3\n", TESTS)
    assert not result.passed
    assert [c.passed for c in result.cases] == [True, False]
    assert "assert" in result.cases[1].message


def test_pytest_import_error_in_solution() -> None:
    result = run_pytest("raise RuntimeError('boom')\n", TESTS)
    assert not result.passed


def test_pytest_infinite_loop() -> None:
    result = run_pytest("while True:\n    pass\n", TESTS, limits=RunLimits(timeout_sec=1.5))
    assert result.run.timed_out
    assert not result.passed


def test_pytest_no_tests_collected_is_not_pass() -> None:
    result = run_pytest("x = 1\n", "x = 1\n")
    assert not result.passed


def test_parse_junit_handles_error_and_skip() -> None:
    xml = """<testsuites><testsuite>
      <testcase name="a"/>
      <testcase name="b"><error message="boom"/></testcase>
      <testcase name="c"><skipped/></testcase>
    </testsuite></testsuites>"""
    cases = parse_junit(xml)
    assert [(c.name, c.passed, c.message) for c in cases] == [
        ("a", True, ""),
        ("b", False, "boom"),
        ("c", False, "skipped"),
    ]
