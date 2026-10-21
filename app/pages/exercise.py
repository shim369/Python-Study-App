"""演習ページ: お題の表示 → コード入力 → 実行・採点 → 結果表示。

採点や「模範解答をいつ見せるか」のルールは core/ にあり、ここは表示と入力の受け渡しだけ。
進捗(挑戦回数・ヒント使用数など)は core.progress で SQLite に保存し、再起動後も復元する。
AI フィードバックは ai/ に任せる。APIキー未設定や API エラーでも、AI 以外はそのまま使える。
"""

import logging
import sqlite3
from collections.abc import Callable
from datetime import date

import streamlit as st
from streamlit_ace import st_ace

from ai.feedback import Feedback, FeedbackService, create_feedback_service
from core.grading import grade
from core.i18n import LANG_KEY, Translator, as_lang
from core.loader import LoadResult, load_all
from core.models import Exercise, GradeResult
from core.practice import PracticeState
from core.progress import ProgressStore, db_path_from_env
from core.srs import ReviewState, review_states

logger = logging.getLogger(__name__)
t = Translator(as_lang(st.session_state.get(LANG_KEY)))  # 画面の文言は t("キー") で引く


@st.cache_resource
def load_exercises() -> LoadResult:
    """教材の読み込みは重くはないが、再実行(rerun)のたびに読み直さないようキャッシュする。"""
    return load_all()


@st.cache_resource
def get_feedback_service() -> FeedbackService | None:
    """AI は1プロセスで1つだけ作る(回答のキャッシュをセッションをまたいで共有するため)。

    .env の APIキーを変えた場合は、アプリを再起動すると反映される。
    """
    return create_feedback_service()


def open_store() -> ProgressStore | None:
    """進捗DBを開く。開けなくても演習はできるよう、None を返して「保存なし」で続ける。"""
    try:
        return ProgressStore(db_path_from_env())
    except (sqlite3.Error, OSError):
        logger.exception("進捗DBを開けません")
        st.warning(t("exercise.db_unavailable"))
        return None


def use_db[T](store: ProgressStore | None, action: Callable[[ProgressStore], T]) -> T | None:
    """DB操作を1つ実行する。失敗しても演習は続けられるよう、通知とログだけ残して None を返す。"""
    if store is None:
        return None
    try:
        return action(store)
    except sqlite3.Error:
        logger.exception("進捗DBの操作に失敗")
        st.toast(t("exercise.db_failed"), icon="⚠️")
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
    """エディタの key。版番号か初期コードの言語が変わると、新しいエディタ(初期コード)になる。"""
    version: int = st.session_state.get(f"editor_version:{exercise.id}", 0)
    starter_lang = st.session_state.setdefault(f"editor_lang:{exercise.id}", t.lang)
    return f"editor:{exercise.id}:{version}:{starter_lang}"


def reset_editor(exercise: Exercise) -> None:
    version_key = f"editor_version:{exercise.id}"
    st.session_state[version_key] = st.session_state.get(version_key, 0) + 1
    st.session_state[f"editor_lang:{exercise.id}"] = t.lang  # 戻すのは表示中の言語の初期コード


def sync_editor_language(original: Exercise) -> None:
    """言語を切り替えたとき、まだ何も書いていなければ初期コードを表示言語のものに差し替える。

    書きかけのコードは消さない(そのときは前の言語の初期コードのコメントが残る)。
    original は言語を切り替える前の Exercise(どちらの言語の初期コードも引ける)。
    """
    lang_key = f"editor_lang:{original.id}"
    starter_lang = as_lang(st.session_state.get(lang_key, t.lang))
    if starter_lang == t.lang:
        return
    code = st.session_state.get(editor_key(original))
    if code is None or code == original.localized(starter_lang).starter_code:
        st.session_state[lang_key] = t.lang


def load_reviews(store: ProgressStore | None) -> dict[str, ReviewState]:
    """復習の状態。採点のたびに変わるのでキャッシュせず、再実行ごとにDBから計算する。"""
    return use_db(store, lambda s: review_states(s.attempt_history())) or {}


def exercise_label(
    exercise: Exercise, store: ProgressStore | None, review: ReviewState | None
) -> str:
    practice = get_practice(exercise, store)
    if review is not None and review.is_due(date.today()):
        mark = "🔁 "
    elif practice.passed:
        mark = "✅ "
    elif practice.attempts:
        mark = "✏️ "
    else:
        mark = ""
    return f"{mark}L{exercise.level} {t(f'level.{exercise.level}')} | {exercise.title}"


# 選択中の問題の id。ダッシュボードの「解く」ボタンもここに書き込む
CURRENT_EXERCISE_KEY = "current_exercise_id"
_SELECTBOX_KEY = "_exercise_selectbox"


def remember_selection(selectbox_key: str) -> None:
    st.session_state[CURRENT_EXERCISE_KEY] = st.session_state[selectbox_key]


def select_exercise(
    exercises: list[Exercise], store: ProgressStore | None, reviews: dict[str, ReviewState]
) -> Exercise:
    """問題を選ぶ。

    widget の値は、その widget が無いページ(ダッシュボード)を表示すると消えてしまう。
    そこで選択は widget ではない別の key に保存し、表示のたびに widget へ書き戻す。
    また selectbox は key が同じだと選択肢の表示名を更新しないので、言語ごとに key を分ける。
    """
    by_id = {ex.id: ex for ex in exercises}
    selectbox_key = f"{_SELECTBOX_KEY}:{t.lang}"
    current = st.session_state.get(CURRENT_EXERCISE_KEY)
    if current in by_id:
        st.session_state[selectbox_key] = current
    # ラベルは先に作っておく(format_func の中で毎回 session_state を引かずに済む)
    labels = {ex.id: exercise_label(ex, store, reviews.get(ex.id)) for ex in exercises}
    selected_id = st.sidebar.selectbox(
        t("exercise.select_label"),
        options=list(by_id),
        format_func=labels.__getitem__,
        key=selectbox_key,
        on_change=remember_selection,
        args=(selectbox_key,),
    )
    return by_id[selected_id]


def render_problem(exercise: Exercise, review: ReviewState | None) -> None:
    st.header(exercise.title)
    if review is not None and review.is_due(date.today()):
        st.info(t("exercise.review_due", number=review.next_review_number))
    tags = " ".join(f"`{tag}`" for tag in exercise.tags)
    level_name = t(f"level.{exercise.level}")
    st.caption(
        t(
            "exercise.meta",
            level=exercise.level,
            level_name=level_name,
            topic=exercise.topic,
            tags=tags,
        )
    )
    if t.lang == "en" and exercise.en is None:  # 英訳がまだ無い教材は日本語のまま表示する
        st.caption(t("exercise.content_language_note"))
    st.markdown(exercise.description)
    if exercise.php_note:
        with st.expander(t("exercise.php_note")):
            st.markdown(exercise.php_note)


def show_next_hint(
    exercise: Exercise, practice: PracticeState, store: ProgressStore | None
) -> None:
    practice.show_next_hint()
    use_db(store, lambda s: s.record_hints(exercise.id, practice.hints_shown))


def render_hints(exercise: Exercise, practice: PracticeState, store: ProgressStore | None) -> None:
    st.subheader(t("exercise.hints"))
    for number, hint in enumerate(exercise.hints[: practice.hints_shown], start=1):
        st.info(t("exercise.hint_item", number=number, hint=hint))
    if practice.has_more_hints:
        label = t("exercise.show_hint", number=practice.hints_shown + 1, total=practice.total_hints)
        st.button(
            label,
            on_click=show_next_hint,
            args=(exercise, practice, store),
            key=f"hint:{exercise.id}",
        )
    else:
        st.caption(t("exercise.no_more_hints"))


def render_result(result: GradeResult) -> None:
    if result.passed:
        st.success(t("exercise.passed", passed=result.passed_count, total=len(result.cases)))
    elif result.timed_out:
        st.error(t("common.timeout"))
    else:
        detail = f" — {result.error_type}" if result.error_type else ""
        st.error(
            t("exercise.failed", passed=result.passed_count, total=len(result.cases), detail=detail)
        )

    st.caption(t("exercise.duration", ms=result.duration_ms))
    if result.truncated:
        st.warning(t("common.truncated"))

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
        with st.expander(t("common.stdout")):
            st.code(result.stdout, language="text")
    if result.stderr.strip():
        with st.expander(t("common.stderr"), expanded=not result.cases):
            st.code(result.stderr, language="text")


def run_grading(
    exercise: Exercise, practice: PracticeState, store: ProgressStore | None, code: str
) -> None:
    with st.spinner(t("common.running")):
        try:
            result = grade(exercise, code)
        except Exception:
            # 採点そのものが壊れた場合(アプリ側の不具合)。学習者のせいではないことを伝える
            logger.exception("採点中に予期しないエラー: %s", exercise.id)
            st.error(t("exercise.grading_error"))
            return
    practice.record(result, code)
    use_db(store, lambda s: s.record_attempt(exercise.id, result))
    # 問題一覧は採点前に描画済み。✏️ / ✅ の印をすぐ反映するため描き直す
    st.rerun()


def ai_log(exercise: Exercise) -> list[tuple[str, Feedback]]:
    """この問題で AI に聞いた内容と回答の履歴(画面表示用。セッション中だけ保持)。"""
    log: list[tuple[str, Feedback]] = st.session_state.setdefault(f"ai_log:{exercise.id}", [])
    return log


def render_ai_assistant(exercise: Exercise, practice: PracticeState, code: str) -> None:
    st.subheader(t("exercise.ai_title"))
    service = get_feedback_service()
    if service is None:
        st.caption(t("exercise.ai_disabled"))
        return

    hint_col, explain_col, review_col = st.columns(3)
    level = practice.next_ai_hint_level
    hint_clicked = hint_col.button(
        (
            t("exercise.ai_hint", level=level, total=practice.total_hints)
            if level
            else t("exercise.ai_hint_used_up")
        ),
        disabled=level is None,
        width="stretch",
    )
    explain_clicked = explain_col.button(
        t("exercise.ai_explain"),
        disabled=not practice.can_explain_failure,
        help=t("exercise.ai_explain_help"),
        width="stretch",
    )
    review_clicked = review_col.button(
        t("exercise.ai_review"),
        disabled=not practice.can_request_review,
        help=t("exercise.ai_review_help"),
        width="stretch",
    )

    log = ai_log(exercise)
    if hint_clicked or explain_clicked or review_clicked:
        with st.spinner(t("common.ai_thinking")):
            if hint_clicked and level is not None:
                # ヒントは「いま書いている途中のコード」を見てもらう
                feedback = service.hint(exercise, code, level, practice.last_result, t.lang)
                if feedback.text:
                    practice.use_ai_hint()  # 失敗した回は段階を進めない
                log.append((t("exercise.ai_log_hint", level=level), feedback))
            elif explain_clicked and practice.last_result is not None:
                feedback = service.explain_failure(
                    exercise, practice.last_code, practice.last_result, t.lang
                )
                log.append((t("exercise.ai_log_explain"), feedback))
            elif review_clicked:
                feedback = service.review(exercise, practice.last_code, t.lang)
                log.append((t("exercise.ai_log_review"), feedback))
        # ボタンは押される前の状態で描画済み。「AIヒント(2/3)」などの表示を更新するため描き直す
        st.rerun()

    # 新しい回答を上に。最新のものだけ開いておく
    for index, (title, feedback) in enumerate(reversed(log)):
        with st.expander(title, expanded=index == 0):
            if feedback.text:
                st.markdown(feedback.text)
            else:
                st.error(feedback.error or t("common.ai_no_answer"))
    if log:
        st.caption(t("exercise.ai_caution"))


def render_solution(
    exercise: Exercise, practice: PracticeState, store: ProgressStore | None
) -> None:
    st.subheader(t("exercise.solution"))
    if practice.can_view_solution:
        st.code(exercise.solution, language="python")
        return
    st.caption(t("exercise.solution_locked"))
    if st.button(t("exercise.show_solution"), key=f"reveal:{exercise.id}"):
        practice.reveal_solution()
        use_db(store, lambda s: s.record_solution_viewed(exercise.id))
        st.rerun()


def main() -> None:
    loaded = load_exercises()
    for error in loaded.errors:
        st.sidebar.error(t("exercise.load_error", name=error.path.parent.name, reason=error.reason))
    if not loaded.exercises:
        st.warning(t("exercise.no_exercises"))
        return

    exercises = [ex.localized(t.lang) for ex in loaded.exercises]  # 問題文などを表示言語に
    store = open_store()
    reviews = load_reviews(store)
    exercise = select_exercise(exercises, store, reviews)
    sync_editor_language(next(ex for ex in loaded.exercises if ex.id == exercise.id))
    practice = get_practice(exercise, store)
    mark_started(exercise, store)

    left, right = st.columns([1, 1], gap="large")
    # 右(エディタ・実行)を先に処理する。合格した同じ実行のうちに左の模範解答を表示するため
    with right:
        st.subheader(t("exercise.code"))
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
        run_clicked = run_col.button(t("common.run"), type="primary", width="stretch")
        reset_col.button(
            t("exercise.reset"),
            on_click=reset_editor,
            args=(exercise,),
            width="stretch",
        )
        if run_clicked:
            run_grading(exercise, practice, store, code)
        if practice.last_result is not None:
            st.caption(t("exercise.attempts", count=practice.attempts))
            render_result(practice.last_result)
        render_ai_assistant(exercise, practice, code)

    with left:
        render_problem(exercise, reviews.get(exercise.id))
        render_hints(exercise, practice, store)
        render_solution(exercise, practice, store)


main()
