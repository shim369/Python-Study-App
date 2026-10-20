"""演習の採点。runner で実行し、結果を GradeResult にまとめる。"""

import re

from core.models import CaseOutcome, Exercise, GradeResult
from runner.pytest_runner import run_pytest, run_script
from runner.sandbox import RunLimits, RunResult

MAX_CODE_CHARS = 20_000

# "ZeroDivisionError: division by zero" のような行から例外名を拾う
_EXCEPTION_RE = re.compile(r"\b([A-Z][A-Za-z]*(?:Error|Exception|Exit|Interrupt))\b")


# pytest の失敗詳細の最終行 "test_solution.py:12: AssertionError" の形式
_PYTEST_LOCATION_RE = re.compile(r":\d+: (\w+)\s*$")


def detect_error_type(text: str) -> str | None:
    """エラーメッセージ中で最後に現れた例外名を返す(トレースバックは最後が原因)。"""
    location = _PYTEST_LOCATION_RE.search(text)
    if location:
        return location.group(1)
    found = _EXCEPTION_RE.findall(text)
    return found[-1] if found else None


def normalize_output(text: str) -> str:
    """行末の空白と末尾の空行を無視して比較できるようにする。"""
    return "\n".join(line.rstrip() for line in text.strip("\n").splitlines())


def _last_line(text: str) -> str:
    lines = text.strip().splitlines()
    return lines[-1] if lines else ""


def grade(exercise: Exercise, code: str) -> GradeResult:
    if len(code) > MAX_CODE_CHARS:
        return GradeResult(
            passed=False,
            stderr=f"コードが長すぎます({MAX_CODE_CHARS}文字まで)",
            error_type="CodeTooLong",
        )
    limits = RunLimits(timeout_sec=exercise.time_limit_sec)
    if exercise.grading == "pytest":
        return _grade_pytest(exercise, code, limits)
    return _grade_io(exercise, code, limits)


def _grade_pytest(exercise: Exercise, code: str, limits: RunLimits) -> GradeResult:
    assert exercise.test_source is not None  # Exercise のバリデーションで保証済み
    result = run_pytest(code, exercise.test_source, limits)
    run = result.run
    cases = [CaseOutcome(c.name, c.passed, c.message, c.details) for c in result.cases]

    error_type: str | None = None
    if run.timed_out:
        error_type = "Timeout"
    elif not result.passed:
        first_failure = next((c for c in cases if not c.passed), None)
        source = (first_failure.details or first_failure.message) if first_failure else ""
        error_type = detect_error_type(source or run.stdout + run.stderr)

    return GradeResult(
        passed=result.passed,
        cases=cases,
        stdout=run.stdout,
        stderr=run.stderr,
        duration_ms=run.duration_ms,
        timed_out=run.timed_out,
        truncated=run.truncated,
        error_type=error_type,
    )


def _grade_io(exercise: Exercise, code: str, limits: RunLimits) -> GradeResult:
    cases: list[CaseOutcome] = []
    stdout_parts: list[str] = []
    stderr = ""
    total_ms = 0
    timed_out = truncated = False
    error_type: str | None = None

    for index, case in enumerate(exercise.cases, start=1):
        name = case.name or f"case{index}"
        run = run_script(code, case.stdin, limits)
        total_ms += run.duration_ms
        truncated = truncated or run.truncated
        stdout_parts.append(f"--- {name} ---\n{run.stdout}")

        if run.timed_out:
            timed_out = True
            error_type = "Timeout"
            cases.append(CaseOutcome(name, False, "タイムアウトしました"))
            break  # 以降のケースも同様にハングする可能性が高いので打ち切る
        if run.returncode != 0:
            stderr = run.stderr
            error_type = error_type or detect_error_type(run.stderr)
            cases.append(CaseOutcome(name, False, _last_line(run.stderr) or "異常終了しました"))
            continue
        if normalize_output(run.stdout) == normalize_output(case.expected_stdout):
            cases.append(CaseOutcome(name, True))
        else:
            error_type = error_type or "WrongAnswer"
            message = f"期待: {case.expected_stdout.strip()!r} / 実際: {run.stdout.strip()!r}"
            cases.append(CaseOutcome(name, False, message))

    return GradeResult(
        passed=bool(cases) and all(c.passed for c in cases) and not timed_out,
        cases=cases,
        stdout="\n".join(stdout_parts),
        stderr=stderr,
        duration_ms=total_ms,
        timed_out=timed_out,
        truncated=truncated,
        error_type=error_type,
    )


def run_free(code: str, stdin: str = "") -> RunResult:
    """お題なしでコードを実行する(「自由に試す」ページ用)。採点はしない。"""
    if len(code) > MAX_CODE_CHARS:
        raise ValueError(f"コードが長すぎます({MAX_CODE_CHARS}文字まで)")
    return run_script(code, stdin, RunLimits())
