"""自由に試すページ: お題なしでコードを書いて実行し、必要なら AI にレビューしてもらう。

実行は演習と同じサンドボックス(runner/)で行う。採点はしないので、進捗DBにも保存しない。
"""

import logging

import streamlit as st
from streamlit_ace import st_ace

from ai.feedback import Feedback, FeedbackService, create_feedback_service
from core.grading import run_free
from runner.sandbox import RunResult

logger = logging.getLogger(__name__)

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
    """AI に渡す実行結果の要約。"""
    if result.timed_out:
        return "タイムアウトしました"
    parts = [f"終了コード: {result.returncode}"]
    if result.stdout.strip():
        parts.append(f"標準出力:\n{result.stdout.strip()}")
    if result.stderr.strip():
        parts.append(f"標準エラー:\n{result.stderr.strip()}")
    return "\n".join(parts)


def render_run_result(result: RunResult) -> None:
    if result.timed_out:
        st.error("⏱ タイムアウトしました。無限ループや重すぎる処理がないか確認しましょう。")
    elif result.ok:
        st.success(f"実行しました({result.duration_ms} ms)")
    else:
        st.error(f"エラーで終了しました(終了コード {result.returncode}、{result.duration_ms} ms)")
    if result.truncated:
        st.warning("出力が多すぎたため、途中で切り詰めました。")
    st.caption("標準出力")
    st.code(result.stdout or "(出力なし)", language="text")
    if result.stderr.strip():
        st.caption("標準エラー")
        st.code(result.stderr, language="text")


def render_ai_review(code: str, result: RunResult | None) -> None:
    st.subheader("🤖 AIレビュー")
    service = get_feedback_service()
    if service is None:
        st.caption("AI機能は無効です。.env に GEMINI_API_KEY を設定して再起動すると使えます。")
        return
    if st.button("このコードをレビューしてもらう"):
        with st.spinner("AI が考えています..."):
            output = summarize_run(result) if result else ""
            st.session_state["playground_review"] = service.free_review(code, output)
    feedback: Feedback | None = st.session_state.get("playground_review")
    if feedback is not None:
        if feedback.text:
            st.markdown(feedback.text)
            st.caption("AI の回答は誤っていることもあります。実行して確かめましょう。")
        else:
            st.error(feedback.error or "AI から回答が得られませんでした。")


def main() -> None:
    st.title("自由に試す")
    st.caption("お題なしで Python を書いて実行できます。結果は保存されません。")

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
    stdin = st.text_area("標準入力(input() で読まれる内容)", value=SAMPLE_STDIN, height=80)

    if st.button("▶ 実行", type="primary"):
        try:
            with st.spinner("実行中..."):
                st.session_state["playground_result"] = run_free(code, stdin)
        except ValueError as e:  # コードが長すぎる
            st.error(str(e))
        except Exception:
            logger.exception("自由実行中に予期しないエラー")
            st.error("実行中にアプリ側でエラーが起きました。ターミナルのログを確認してください。")

    result: RunResult | None = st.session_state.get("playground_result")
    if result is not None:
        render_run_result(result)
    render_ai_review(code, result)


main()
