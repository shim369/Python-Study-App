"""演習ページ: お題の表示 → コード入力 → 実行・採点 → 結果表示。

採点や「模範解答をいつ見せるか」のルールは core/ にあり、ここは表示と入力の受け渡しだけ。
"""

import logging

import streamlit as st
from streamlit_ace import st_ace

from core.grading import grade
from core.loader import LoadResult, load_all
from core.models import Exercise, GradeResult
from core.practice import PracticeState

logger = logging.getLogger(__name__)


@st.cache_resource
def load_exercises() -> LoadResult:
    """教材の読み込みは重くはないが、再実行(rerun)のたびに読み直さないようキャッシュする。"""
    return load_all()


def get_practice(exercise: Exercise) -> PracticeState:
    """問題ごとの状態を session_state に保持する(問題を切り替えても状態が残る)。"""
    key = f"practice:{exercise.id}"
    if key not in st.session_state:
        st.session_state[key] = PracticeState(total_hints=len(exercise.hints))
    state: PracticeState = st.session_state[key]
    return state


def editor_key(exercise: Exercise) -> str:
    """エディタの key。版番号を上げると新しいウィジェットになり、初期コードに戻る。"""
    version: int = st.session_state.get(f"editor_version:{exercise.id}", 0)
    return f"editor:{exercise.id}:{version}"


def reset_editor(exercise: Exercise) -> None:
    version_key = f"editor_version:{exercise.id}"
    st.session_state[version_key] = st.session_state.get(version_key, 0) + 1


def exercise_label(exercise: Exercise) -> str:
    mark = "✅ " if get_practice(exercise).passed else ""
    return f"{mark}L{exercise.level} {exercise.level_name} | {exercise.title}"


def select_exercise(exercises: list[Exercise]) -> Exercise:
    by_id = {ex.id: ex for ex in exercises}
    selected_id = st.sidebar.selectbox(
        "問題",
        options=list(by_id),
        format_func=lambda exercise_id: exercise_label(by_id[exercise_id]),
        key="selected_exercise_id",
    )
    return by_id[selected_id]


def render_problem(exercise: Exercise) -> None:
    st.title(exercise.title)
    tags = " ".join(f"`{tag}`" for tag in exercise.tags)
    st.caption(f"レベル{exercise.level}({exercise.level_name})・トピック: {exercise.topic}  {tags}")
    st.markdown(exercise.description)
    if exercise.php_note:
        with st.expander("🐘 PHPとの違い"):
            st.markdown(exercise.php_note)


def render_hints(exercise: Exercise, practice: PracticeState) -> None:
    st.subheader("ヒント")
    for number, hint in enumerate(exercise.hints[: practice.hints_shown], start=1):
        st.info(f"**ヒント{number}**: {hint}")
    if practice.has_more_hints:
        label = f"ヒント{practice.hints_shown + 1}を見る(全{practice.total_hints}段階)"
        st.button(label, on_click=practice.show_next_hint, key=f"hint:{exercise.id}")
    else:
        st.caption("ヒントはこれで全部です。")


def render_result(result: GradeResult) -> None:
    if result.passed:
        st.success(f"🎉 合格!({result.passed_count}/{len(result.cases)} ケース)")
    elif result.timed_out:
        st.error("⏱ タイムアウトしました。無限ループや重すぎる処理がないか確認しましょう。")
    else:
        detail = f" — {result.error_type}" if result.error_type else ""
        st.error(f"不合格({result.passed_count}/{len(result.cases)} ケース){detail}")

    st.caption(f"実行時間: {result.duration_ms} ms")
    if result.truncated:
        st.warning("出力が多すぎたため、途中で切り詰めました。")

    for case in result.cases:
        icon = "✅" if case.passed else "❌"
        with st.expander(f"{icon} {case.name}", expanded=not case.passed):
            if case.message:
                st.code(case.message, language="text")
            if case.details:
                st.code(case.details, language="text")
            if case.passed and not case.message:
                st.write("OK")

    if result.stdout.strip():
        with st.expander("標準出力"):
            st.code(result.stdout, language="text")
    if result.stderr.strip():
        with st.expander("標準エラー", expanded=not result.cases):
            st.code(result.stderr, language="text")


def run_grading(exercise: Exercise, practice: PracticeState, code: str) -> None:
    with st.spinner("実行中..."):
        try:
            result = grade(exercise, code)
        except Exception:
            # 採点そのものが壊れた場合(アプリ側の不具合)。学習者のせいではないことを伝える
            logger.exception("採点中に予期しないエラー: %s", exercise.id)
            st.error("採点中にアプリ側でエラーが起きました。ターミナルのログを確認してください。")
            return
    practice.record(result)


def render_solution(exercise: Exercise, practice: PracticeState) -> None:
    st.subheader("模範解答")
    if practice.can_view_solution:
        st.code(exercise.solution, language="python")
        return
    st.caption("合格すると表示されます。どうしても分からないときだけ開きましょう。")
    if st.button("模範解答を見る", key=f"reveal:{exercise.id}"):
        practice.reveal_solution()
        st.rerun()


def main() -> None:
    loaded = load_exercises()
    for error in loaded.errors:
        st.sidebar.error(f"教材の読み込みに失敗: {error.path.parent.name}\n\n{error.reason}")
    if not loaded.exercises:
        st.warning("演習がありません。exercises/ に教材を追加してください。")
        return

    exercise = select_exercise(loaded.exercises)
    practice = get_practice(exercise)

    left, right = st.columns([1, 1], gap="large")
    # 右(エディタ・実行)を先に処理する。合格した同じ実行のうちに左の模範解答を表示するため
    with right:
        st.subheader("コード")
        # auto_update=True: 入力の度に値が送られるので「実行」時に最新のコードが使われる
        code: str = st_ace(
            value=exercise.starter_code,
            language="python",
            theme="tomorrow_night",
            min_lines=16,
            tab_size=4,
            wrap=True,
            auto_update=True,
            key=editor_key(exercise),
        )
        run_col, reset_col = st.columns([1, 1])
        run_clicked = run_col.button("▶ 実行", type="primary", width="stretch")
        reset_col.button(
            "初期コードに戻す",
            on_click=reset_editor,
            args=(exercise,),
            width="stretch",
        )
        if run_clicked:
            run_grading(exercise, practice, code)
        if practice.last_result is not None:
            st.caption(f"挑戦回数: {practice.attempts}")
            render_result(practice.last_result)

    with left:
        render_problem(exercise)
        render_hints(exercise, practice)
        render_solution(exercise, practice)


main()
