"""1問に取り組んでいる間の状態(ヒントの開示数・模範解答の表示可否・直近の採点結果・AIの利用状況)。

UI(Streamlit)はこのクラスを session_state に置いて使うだけにし、
「いつ模範解答を見せてよいか」などのルールはここに集める。
"""

from dataclasses import dataclass
from typing import Self

from core.models import GradeResult
from core.progress import ExerciseProgress, Status


@dataclass
class PracticeState:
    total_hints: int
    hints_shown: int = 0
    attempts: int = 0
    passed: bool = False
    solution_revealed: bool = False
    last_result: GradeResult | None = None
    last_code: str = ""  # last_result を出したコード(AIに原因解説・レビューを頼む時に使う)
    ai_hints_used: int = 0

    @classmethod
    def from_progress(cls, total_hints: int, progress: ExerciseProgress | None) -> Self:
        """保存済みの進捗から状態を復元する(アプリを再起動しても続きから取り組める)。"""
        if progress is None:
            return cls(total_hints=total_hints)
        return cls(
            total_hints=total_hints,
            hints_shown=min(progress.hints_used, total_hints),
            attempts=progress.attempts,
            passed=progress.status is Status.PASSED,
            solution_revealed=progress.solution_viewed,
        )

    def record(self, result: GradeResult, code: str) -> None:
        """採点結果を記録する。一度合格したら、後で不合格になっても合格扱いのまま。"""
        self.attempts += 1
        self.last_result = result
        self.last_code = code
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

    # --- AI フィードバック ----------------------------------------------------

    @property
    def next_ai_hint_level(self) -> int | None:
        """次に頼めるAIヒントの段階(1〜total_hints)。使い切ったら None。"""
        if self.ai_hints_used >= self.total_hints:
            return None
        return self.ai_hints_used + 1

    def use_ai_hint(self) -> None:
        if self.next_ai_hint_level is not None:
            self.ai_hints_used += 1

    @property
    def can_explain_failure(self) -> bool:
        """直近の実行が不合格なら、その原因の解説を頼める。"""
        return self.last_result is not None and not self.last_result.passed

    @property
    def can_request_review(self) -> bool:
        """直近の実行で合格したコードがあれば、レビューを頼める。"""
        return self.last_result is not None and self.last_result.passed
