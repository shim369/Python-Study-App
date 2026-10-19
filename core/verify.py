"""教材の自己検証: 模範解答は合格し、初期コードは不合格になること。

初期コードが合格してしまう演習は「何も書かなくても通る」=テストに抜け穴がある。
"""

from dataclasses import dataclass

from core.grading import grade
from core.models import Exercise, GradeResult


@dataclass(frozen=True)
class VerifyReport:
    exercise: Exercise
    solution: GradeResult
    starter: GradeResult

    @property
    def problems(self) -> list[str]:
        problems: list[str] = []
        if not self.solution.passed:
            failed = [c.name for c in self.solution.cases if not c.passed]
            detail = ", ".join(failed) or self.solution.error_type or "実行エラー"
            problems.append(f"模範解答が不合格: {detail}")
        if self.starter.passed:
            problems.append("初期コードのままで合格してしまう(テストが弱い)")
        return problems

    @property
    def ok(self) -> bool:
        return not self.problems


def verify_exercise(exercise: Exercise) -> VerifyReport:
    return VerifyReport(
        exercise=exercise,
        solution=grade(exercise, exercise.solution),
        starter=grade(exercise, exercise.starter_code),
    )
