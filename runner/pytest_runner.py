"""学習者コードを solution.py として配置し、演習のテストを pytest で実行する。"""

import tempfile
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path

from runner.sandbox import RunLimits, RunResult, run_python

SOLUTION_FILE = "solution.py"
TEST_FILE = "test_solution.py"


@dataclass(frozen=True)
class CaseResult:
    name: str
    passed: bool
    message: str = ""  # 1行の要約(例: "assert 3 == 4")
    details: str = ""  # トレースバック全文(末尾に "file:line: 例外名" が入る)


@dataclass(frozen=True)
class PytestRun:
    run: RunResult
    cases: list[CaseResult]

    @property
    def passed(self) -> bool:
        return self.run.ok and bool(self.cases) and all(c.passed for c in self.cases)


def parse_junit(xml_text: str) -> list[CaseResult]:
    """pytest の --junitxml 出力からテストケースごとの結果を取り出す。"""
    root = ET.fromstring(xml_text)
    results: list[CaseResult] = []
    for case in root.iter("testcase"):
        name = case.get("name", "?")
        problem = case.find("failure")
        if problem is None:
            problem = case.find("error")
        skipped = case.find("skipped")
        if problem is not None:
            details = (problem.text or "").strip()
            message = problem.get("message") or details
            results.append(CaseResult(name, passed=False, message=message, details=details))
        elif skipped is not None:
            results.append(CaseResult(name, passed=False, message="skipped"))
        else:
            results.append(CaseResult(name, passed=True))
    return results


def run_pytest(code: str, test_source: str, limits: RunLimits | None = None) -> PytestRun:
    with (
        tempfile.TemporaryDirectory(prefix="study-run-") as workdir,
        tempfile.TemporaryDirectory(prefix="study-report-") as report_dir,
    ):
        work = Path(workdir)
        (work / SOLUTION_FILE).write_text(code, encoding="utf-8")
        (work / TEST_FILE).write_text(test_source, encoding="utf-8")
        # プロジェクト側の pytest 設定を拾わないよう、空の設定ファイルを置く
        (work / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
        report = Path(report_dir) / "report.xml"

        run = run_python(
            [
                "-m",
                "pytest",
                TEST_FILE,
                "-q",
                "--no-header",
                "-p",
                "no:cacheprovider",
                f"--junitxml={report}",
            ],
            workdir=work,
            limits=limits,
        )

        cases: list[CaseResult] = []
        if report.exists():
            try:
                cases = parse_junit(report.read_text(encoding="utf-8"))
            except ET.ParseError:
                cases = []
    return PytestRun(run=run, cases=cases)


def run_script(code: str, stdin: str, limits: RunLimits | None = None) -> RunResult:
    """solution.py を標準入力つきでそのまま実行する(input/output 形式の採点用)。"""
    with tempfile.TemporaryDirectory(prefix="study-run-") as workdir:
        work = Path(workdir)
        (work / SOLUTION_FILE).write_text(code, encoding="utf-8")
        return run_python([SOLUTION_FILE], workdir=work, stdin=stdin, limits=limits)
