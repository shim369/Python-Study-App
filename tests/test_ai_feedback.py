import re

import pytest

from ai.client import AIError
from ai.feedback import (
    MAX_CODE_CHARS,
    PROMPTS_DIR,
    FeedbackService,
    clip,
    load_prompt,
    summarize_result,
)
from core.i18n import LANGUAGES, Lang, translate
from core.loader import load_all
from core.models import CaseOutcome, GradeResult

EXERCISE = load_all().exercises[0]
FAILED = GradeResult(
    passed=False,
    cases=[CaseOutcome("test_ok", True), CaseOutcome("test_ng", False, "assert 1 == 2", "詳細")],
    stderr="Traceback ...\nAssertionError",
    error_type="AssertionError",
)


class FakeGenerator:
    """Gemini の代わりに、受け取ったプロンプトを記録して決まった文を返す。"""

    def __init__(self, error: str | None = None) -> None:
        self.calls: list[tuple[str, str]] = []
        self.error = error

    def generate(self, system: str, prompt: str) -> str:
        self.calls.append((system, prompt))
        if self.error:
            raise AIError(self.error)
        return f"回答{len(self.calls)}"


@pytest.mark.parametrize("lang", LANGUAGES)
@pytest.mark.parametrize("name", ["system", "hint", "explain_failure", "review", "free_review"])
def test_prompt_templates_exist(name: str, lang: str) -> None:
    assert (PROMPTS_DIR / lang / f"{name}.md").read_text(encoding="utf-8").strip()


@pytest.mark.parametrize("name", ["hint", "explain_failure", "review", "free_review"])
def test_prompt_placeholders_match_between_languages(name: str) -> None:
    """英語版のプロンプトにも、同じ $変数 が揃っていること(足りないと substitute で落ちる)。"""

    def placeholders(lang: Lang) -> set[str]:
        return set(re.findall(r"\$(\w+)", load_prompt(name, lang).template))

    assert placeholders("en") == placeholders("ja")


def test_hint_prompt_contains_level_code_and_result() -> None:
    fake = FakeGenerator()
    feedback = FeedbackService(fake).hint(EXERCISE, "def f(): pass", 2, FAILED)

    assert feedback.text == "回答1"
    system, prompt = fake.calls[0]
    assert system == load_prompt("system").template
    assert "段階 2 / 3" in prompt
    assert EXERCISE.title in prompt
    assert "def f(): pass" in prompt
    assert "assert 1 == 2" in prompt
    assert EXERCISE.solution not in prompt  # ヒントでは模範解答を渡さない(漏れ防止)


def test_hint_level_out_of_range() -> None:
    with pytest.raises(ValueError):
        FeedbackService(FakeGenerator()).hint(EXERCISE, "", 4, None)


def test_explain_failure_does_not_send_solution() -> None:
    fake = FakeGenerator()
    FeedbackService(fake).explain_failure(EXERCISE, "x = 1", FAILED)
    prompt = fake.calls[0][1]
    assert "x = 1" in prompt
    assert "AssertionError" in prompt
    assert EXERCISE.solution not in prompt


def test_review_sends_solution_as_reference() -> None:
    fake = FakeGenerator()
    FeedbackService(fake).review(EXERCISE, "x = 1")
    assert EXERCISE.solution in fake.calls[0][1]


def test_code_with_dollar_and_braces_is_sent_as_is() -> None:
    fake = FakeGenerator()
    code = 'print(f"{x}") # $level ${title}'
    FeedbackService(fake).review(EXERCISE, code)
    assert code in fake.calls[0][1]


def test_same_request_is_cached() -> None:
    fake = FakeGenerator()
    service = FeedbackService(fake)
    first = service.review(EXERCISE, "x = 1")
    second = service.review(EXERCISE, "x = 1")
    third = service.review(EXERCISE, "x = 2")
    assert first == second
    assert third.text == "回答2"
    assert len(fake.calls) == 2


def test_english_uses_english_prompts() -> None:
    """英語表示のときは英語のプロンプトで聞く。言語が違えば別の回答としてキャッシュする。"""
    fake = FakeGenerator()
    service = FeedbackService(fake)
    service.explain_failure(EXERCISE, "x = 1", FAILED)
    service.explain_failure(EXERCISE, "x = 1", FAILED, lang="en")
    assert len(fake.calls) == 2
    system, prompt = fake.calls[1]
    assert system == load_prompt("system", "en").template
    assert "Answer in English" in system
    assert "Failed (error type: AssertionError)" in prompt  # 実行結果の要約も英語


def test_error_message_follows_lang() -> None:
    service = FeedbackService(FakeGenerator(error="ai_error.rate_limit"))
    assert service.review(EXERCISE, "x = 1", lang="en").error == translate(
        "en", "ai_error.rate_limit"
    )


def test_error_is_returned_not_raised_and_not_cached() -> None:
    fake = FakeGenerator(error="ai_error.rate_limit")
    service = FeedbackService(fake)
    feedback = service.review(EXERCISE, "x = 1")
    assert feedback.text is None
    assert feedback.error == translate("ja", "ai_error.rate_limit")

    fake.error = None
    assert service.review(EXERCISE, "x = 1").text is not None  # 失敗はキャッシュしない


def test_long_code_is_clipped() -> None:
    fake = FakeGenerator()
    FeedbackService(fake).review(EXERCISE, "a" * (MAX_CODE_CHARS + 500))
    prompt = fake.calls[0][1]
    assert "a" * (MAX_CODE_CHARS + 1) not in prompt
    assert "500 文字省略" in prompt


def test_clip_keeps_short_text() -> None:
    assert clip("abc", 3) == "abc"
    assert clip("abcd", 3).startswith("abc\n")


def test_summarize_result_in_english() -> None:
    assert summarize_result(None, "en") == "(not run yet)"
    assert summarize_result(GradeResult(passed=True), "en") == "Passed"


def test_summarize_result() -> None:
    assert summarize_result(None) == "(まだ実行していません)"
    assert summarize_result(GradeResult(passed=True)) == "合格"
    summary = summarize_result(FAILED)
    assert "不合格(エラー種別: AssertionError)" in summary
    assert "test_ng: assert 1 == 2" in summary
    assert "test_ok" not in summary  # 合格したケースは送らない
    assert "Traceback" in summary


def test_free_review_sends_code_and_output() -> None:
    fake = FakeGenerator()
    FeedbackService(fake).free_review("print(1)", "標準出力:\n1")
    prompt = fake.calls[0][1]
    assert "print(1)" in prompt
    assert "標準出力:\n1" in prompt


def test_free_review_without_output() -> None:
    fake = FakeGenerator()
    FeedbackService(fake).free_review("x = 1", "")
    assert "(まだ実行していません)" in fake.calls[0][1]
