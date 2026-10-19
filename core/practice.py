"""1問に取り組んでいる間の状態(ヒントの開示数・模範解答の表示可否・直近の採点結果)。

UI(Streamlit)はこのクラスを session_state に置いて使うだけにし、
「いつ模範解答を見せてよいか」などのルールはここに集める。
"""

from dataclasses import dataclass

from core.models import GradeResult


@dataclass
class PracticeState:
    total_hints: int
    hints_shown: int = 0
    attempts: int = 0
    passed: bool = False
    solution_revealed: bool = False
    last_result: GradeResult | None = None

    def record(self, result: GradeResult) -> None:
        """採点結果を記録する。一度合格したら、後で不合格になっても合格扱いのまま。"""
        self.attempts += 1
        self.last_result = result
        self.passed = self.passed or result.passed

    @property
    def has_more_hints(self) -> bool:
        return self.hints_shown < self.total_hints

    def show_next_hint(self) -> None:
        if self.has_more_hints:
            self.hints_shown += 1

    def reveal_solution(self) -> None:
        self.solution_revealed = True

    @property
    def can_view_solution(self) -> bool:
        """模範解答は、合格後か、学習者が明示的に「見る」を選んだ後にだけ表示する。"""
        return self.passed or self.solution_revealed
