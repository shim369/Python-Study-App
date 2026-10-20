"""演習ページ: お題の表示 → コード入力 → 実行・採点 → 結果表示。

採点や「模範解答をいつ見せるか」のルールは core/ にあり、ここは表示と入力の受け渡しだけ。
進捗(挑戦回数・ヒント使用数など)は core.progress で SQLite に保存し、再起動後も復元する。
"""

import logging
import sqlite3
from collections.abc import Callable

import streamlit as st
from streamlit_ace import st_ace

from core.grading import grade
from core.loader import LoadResult, load_all
from core.models import Exercise, GradeResult
from core.practice import PracticeState
from core.progress import ProgressStore, db_path_from_env

logger = logging.getLogger(__name__)


@st.cache_resource
def load_exercises() -> LoadResult:
    """教材の読み込みは重くはないが、再実行(rerun)のたびに読み直さないようキャッシュする。"""
    return load_all()


def open_store() -> ProgressStore | None:
    """進捗DBを開く。開けなくても演習はできるよう、None を返して「保存なし」で続ける。"""
    try:
        return ProgressStore(db_path_from_env())
    except (sqlite3.Error, OSError):
        logger.exception("進捗DBを開けません")
        st.warning("進捗DBを開けないため、今回の結果は保存されません。ログを確認してください。")
        return None


def use_db[T](store: ProgressStore | None, action: Callable[[ProgressStore], T]) -> T | None:
    """DB操作を1つ実行する。失敗しても演習は続けられるよう、通知とログだけ残して None を返す。"""
    if store is None:
        return None
    try:
        return action(store)
    except sqlite3.Error:
        logger.exception("進捗DBの操作に失敗")
        st.toast("進捗を保存・読み込みできませんでした。ログを確認してください。", icon="⚠️")
        return None


def get_practice(exercise: Exercise, store: ProgressStore | None) -> PracticeState:
    """問題ごとの状態を session_state に保持する(問題を切り替えても状態が残る)。

    セッションで初めて触る問題は、DBに保存された進捗から復元する。
    """
    key = f"practice:{exercise.id}"
    if key not in st.session_state:
        saved = use_db(store, lambda s: s.get(exercise.id))
        st.session_state[key] = PracticeState.from_progress(len(exercise.hints), saved)
    state: PracticeState = st.session_state[key]
    return state


def mark_started(exercise: Exercise, store: ProgressStore | None) -> None:
    """「問題を開いた日時」を記録する。DBへの書き込みは1セッションにつき1回で十分。"""
    key = f"started:{exercise.id}"
    if not st.session_state.get(key):
        use_db(store, lambda s: s.start(exercise.id))
        st.session_state[key] = True


def editor_key(exercise: Exercise) -> str:
    """エディタの key。版番号を上げると新しいウィジェットになり、初期コードに戻る。"""
    version: int = st.session_state.get(f"editor_version:{exercise.id}", 0)
    return f"editor:{exercise.id}:{version}"


def reset_editor(exercise: Exercise) -> None:
    version_key = f"editor_version:{exercise.id}"
    st.session_state[version_key] = st.session_state.get(version_key, 0) + 1


def exercise_label(exercise: Exercise, store: ProgressStore | None) -> str:
    practice = get_practice(exercise, store)
    mark = "✅ " if practice.passed else "✏️ " if practice.attempts else ""
    return f"{mark}L{exercise.level} {exercise.level_name} | {exercise.title}"


def select_exercise(exercises: list[Exercise], store: ProgressStore | None) -> Exercise:
    by_id = {ex.id: ex for ex in exercises}
    selected_id = st.sidebar.selectbox(
        "問題",
        options=list(by_id),
        format_func=lambda exercise_id: exercise_label(by_id[exercise_id], store),
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


def show_next_hint(
    exercise: Exercise, practice: PracticeState, store: ProgressStore | None
) -> None:
    practice.show_next_hint()
    use_db(store, lambda s: s.record_hints(exercise.id, practice.hints_shown))


def render_hints(exercise: Exercise, practice: PracticeState, store: ProgressStore | None) -> None:
    st.subheader("ヒント")
    for number, hint in enumerate(exercise.hints[: practice.hints_shown], start=1):
        st.info(f"**ヒント{number}**: {hint}")
    if practice.has_more_hints:
        label = f"ヒント{practice.hints_shown + 1}を見る(全{practice.total_hints}段階)"
        st.button(
            label,
            on_click=show_next_hint,
            args=(exercise, practice, store),
            key=f"hint:{exercise.id}",
        )
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


def run_grading(
    exercise: Exercise, practice: PracticeState, store: ProgressStore | None, code: str
) -> None:
    with st.spinner("実行中..."):
        try:
            result = grade(exercise, code)
        except Exception:
            # 採点そのものが壊れた場合(アプリ側の不具合)。学習者のせいではないことを伝える
            logger.exception("採点中に予期しないエラー: %s", exercise.id)
            st.error("採点中にアプリ側でエラーが起きました。ターミナルのログを確認してください。")
            return
    practice.record(result)
    use_db(store, lambda s: s.record_attempt(exercise.id, result))


def render_solution(
    exercise: Exercise, practice: PracticeState, store: ProgressStore | None
) -> None:
    st.subheader("模範解答")
    if practice.can_view_solution:
        st.code(exercise.solution, language="python")
        return
    st.caption("合格すると表示されます。どうしても分からないときだけ開きましょう。")
    if st.button("模範解答を見る", key=f"reveal:{exercise.id}"):
        practice.reveal_solution()
        use_db(store, lambda s: s.record_solution_viewed(exercise.id))
        st.rerun()


def main() -> None:
    loaded = load_exercises()
    for error in loaded.errors:
        st.sidebar.error(f"教材の読み込みに失敗: {error.path.parent.name}\n\n{error.reason}")
    if not loaded.exercises:
        st.warning("演習がありません。exercises/ に教材を追加してください。")
        return

    store = open_store()
    exercise = select_exercise(loaded.exercises, store)
    practice = get_practice(exercise, store)
    mark_started(exercise, store)

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
            run_grading(exercise, practice, store, code)
        if practice.last_result is not None:
            st.caption(f"挑戦回数: {practice.attempts}")
            render_result(practice.last_result)

    with left:
        render_problem(exercise)
        render_hints(exercise, practice, store)
        render_solution(exercise, practice, store)


main()
