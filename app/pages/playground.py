"""自由に試すページ: お題なしでコードを書いて実行し、必要なら AI にレビューしてもらう。

実行は演習と同じサンドボックス(runner/)で行う。採点はしないので、進捗DBにも保存しない。
"""

import logging

import streamlit as st
from streamlit_ace import st_ace

from ai.feedback import Feedback, FeedbackService, create_feedback_service
from core.grading import run_free
from core.i18n import LANG_KEY, Translator, as_lang
from runner.sandbox import RunResult

logger = logging.getLogger(__name__)
t = Translator(as_lang(st.session_state.get(LANG_KEY)))  # 画面の文言は t("キー") で引く

SAMPLE_CODE = """from collections import Counter

words = input().split()
for word, count in Counter(words).most_common(3):
    print(f"{word}: {count}")
"""
SAMPLE_STDIN = "python php python go python php"


@st.cache_resource
def get_feedback_service() -> FeedbackService | None:
    return create_feedback_service()


def summarize_run(result: RunResult) -> str:
    """AI に渡す実行結果の要約(表示中の言語で書く)。"""
    if result.timed_out:
        return t("ai_input.timed_out")
    parts = [t("ai_input.exit_code", code=result.returncode)]
    if result.stdout.strip():
        parts.append(f"{t('ai_input.stdout')}:\n{result.stdout.strip()}")
    if result.stderr.strip():
        parts.append(f"{t('ai_input.stderr')}:\n{result.stderr.strip()}")
    return "\n".join(parts)


def render_run_result(result: RunResult) -> None:
    if result.timed_out:
        st.error(t("common.timeout"))
    elif result.ok:
        st.success(t("playground.ran", ms=result.duration_ms))
    else:
        st.error(t("playground.exited_with_error", code=result.returncode, ms=result.duration_ms))
    if result.truncated:
        st.warning(t("common.truncated"))
    st.caption(t("common.stdout"))
    st.code(result.stdout or t("playground.no_output"), language="text")
    if result.stderr.strip():
        st.caption(t("common.stderr"))
        st.code(result.stderr, language="text")


def render_ai_review(code: str, result: RunResult | None) -> None:
    st.subheader(t("playground.ai_title"))
    service = get_feedback_service()
    if service is None:
        st.caption(t("playground.ai_disabled"))
        return
    if st.button(t("playground.ai_review")):
        with st.spinner(t("common.ai_thinking")):
            output = summarize_run(result) if result else ""
            st.session_state["playground_review"] = service.free_review(code, output, t.lang)
    feedback: Feedback | None = st.session_state.get("playground_review")
    if feedback is not None:
        if feedback.text:
            st.markdown(feedback.text)
            st.caption(t("playground.ai_caution"))
        else:
            st.error(feedback.error or t("common.ai_no_answer"))


def main() -> None:
    st.header(t("playground.title"))
    st.caption(t("playground.caption"))

    code: str = st_ace(
        value=SAMPLE_CODE,
        language="python",
        theme="tomorrow_night",
        min_lines=14,
        tab_size=4,
        wrap=True,
        auto_update=True,
        key="playground_editor",
    )
    stdin = st.text_area(t("playground.stdin"), value=SAMPLE_STDIN, height=80)

    if st.button(t("common.run"), type="primary"):
        try:
            with st.spinner(t("common.running")):
                st.session_state["playground_result"] = run_free(code, stdin)
        except ValueError as e:  # コードが長すぎる
            st.error(str(e))
        except Exception:
            logger.exception("自由実行中に予期しないエラー")
            st.error(t("common.app_error_log"))

    result: RunResult | None = st.session_state.get("playground_result")
    if result is not None:
        render_run_result(result)
    render_ai_review(code, result)


main()
