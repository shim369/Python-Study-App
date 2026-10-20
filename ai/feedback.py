"""AI フィードバック(段階的ヒント・不合格の原因解説・合格後のコードレビュー)。

プロンプト文は prompts/ のテンプレートに置き、ここでは値を埋めて送るだけにする。
テンプレートは string.Template($name 形式)を使う。コード中の { } と衝突しないため。

トークン節約のため、送るコードと実行結果は長さを制限し、
同じ入力への回答はメモリ上にキャッシュして再利用する。
"""

import hashlib
from dataclasses import dataclass
from pathlib import Path
from string import Template

from ai.client import AIError, TextGenerator, create_client
from core.models import Exercise, GradeResult

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
MAX_CODE_CHARS = 4_000
MAX_RESULT_CHARS = 1_500
MAX_CACHE_ENTRIES = 100
HINT_LEVELS = 3


def load_prompt(name: str) -> Template:
    return Template((PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8"))


def clip(text: str, limit: int) -> str:
    """長すぎる入力は先頭だけ送る(切ったことは AI にも分かるようにする)。"""
    if len(text) <= limit:
        return text
    return text[:limit] + f"\n... (以下 {len(text) - limit} 文字省略)"


def summarize_result(result: GradeResult | None) -> str:
    """採点結果を、AI に渡す短いテキストにまとめる。"""
    if result is None:
        return "(まだ実行していません)"
    lines = ["合格" if result.passed else f"不合格(エラー種別: {result.error_type or '不明'})"]
    for case in result.cases:
        if not case.passed:
            lines.append(f"- {case.name}: {case.message}")
            if case.details:
                lines.append(case.details)
    if result.stderr.strip():
        lines.append(f"標準エラー:\n{result.stderr.strip()}")
    return clip("\n".join(lines), MAX_RESULT_CHARS)


@dataclass(frozen=True)
class Feedback:
    """AI の回答。失敗時は text が None で、error に画面表示用のメッセージが入る。"""

    text: str | None = None
    error: str | None = None


class FeedbackService:
    def __init__(self, generator: TextGenerator) -> None:
        self._generator = generator
        self._system = load_prompt("system").template
        self._cache: dict[str, str] = {}

    def hint(
        self, exercise: Exercise, code: str, level: int, last_result: GradeResult | None
    ) -> Feedback:
        if not 1 <= level <= HINT_LEVELS:
            raise ValueError(f"ヒントの段階は 1〜{HINT_LEVELS} です: {level}")
        return self._ask(
            "hint",
            level=str(level),
            title=exercise.title,
            description=exercise.description,
            code=clip(code, MAX_CODE_CHARS),
            result=summarize_result(last_result),
        )

    def explain_failure(self, exercise: Exercise, code: str, result: GradeResult) -> Feedback:
        return self._ask(
            "explain_failure",
            title=exercise.title,
            description=exercise.description,
            code=clip(code, MAX_CODE_CHARS),
            result=summarize_result(result),
        )

    def review(self, exercise: Exercise, code: str) -> Feedback:
        return self._ask(
            "review",
            title=exercise.title,
            description=exercise.description,
            code=clip(code, MAX_CODE_CHARS),
            solution=exercise.solution,
        )

    def free_review(self, code: str, output: str) -> Feedback:
        """お題のないコードのレビュー(「自由に試す」ページ用)。output は実行結果の要約。"""
        return self._ask(
            "free_review",
            code=clip(code, MAX_CODE_CHARS),
            output=clip(output, MAX_RESULT_CHARS) if output else "(まだ実行していません)",
        )

    def _ask(self, prompt_name: str, **values: str) -> Feedback:
        prompt = load_prompt(prompt_name).substitute(values)
        key = hashlib.sha256(prompt.encode()).hexdigest()
        if key in self._cache:
            return Feedback(text=self._cache[key])
        try:
            text = self._generator.generate(self._system, prompt)
        except AIError as e:  # ログは client 側で記録済み。画面に出すメッセージだけ返す
            return Feedback(error=str(e))

        if len(self._cache) >= MAX_CACHE_ENTRIES:
            self._cache.pop(next(iter(self._cache)))  # いちばん古いものを捨てる
        self._cache[key] = text
        return Feedback(text=text)


def create_feedback_service() -> FeedbackService | None:
    """APIキーが設定されていれば FeedbackService を作る。未設定なら None(AI機能なし)。"""
    client = create_client()
    return FeedbackService(client) if client else None
