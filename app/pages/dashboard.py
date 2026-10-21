"""ダッシュボード: 今日やること(おすすめ・復習)・苦手トピック・習熟度・問題ごとの状態・履歴。

集計は core/(dashboard・srs・recommend)、データの読み込みは core/progress.py が担当し、
ここは表示だけ。
"""

import logging
import sqlite3
from datetime import date, datetime

import streamlit as st

from core.dashboard import format_duration, status_of, study_streak, topic_mastery
from core.export import attempts_to_csv, progress_to_json
from core.i18n import LANG_KEY, Translator, as_lang
from core.loader import load_all
from core.models import Exercise
from core.progress import AttemptRecord, ExerciseProgress, ProgressStore, Status, db_path_from_env
from core.recommend import recommend, weak_topics
from core.srs import ReviewState, review_states

logger = logging.getLogger(__name__)
t = Translator(as_lang(st.session_state.get(LANG_KEY)))  # 画面の文言は t("キー") で引く

RECENT_LIMIT = 15
RECOMMEND_LIMIT = 5
STATUS_ICONS = {Status.NOT_STARTED: "⬜", Status.IN_PROGRESS: "✏️", Status.PASSED: "✅"}


def render_summary(
    exercises: list[Exercise], progress: dict[str, ExerciseProgress], study_dates: set[date]
) -> None:
    passed = sum(status_of(ex.id, progress) is Status.PASSED for ex in exercises)
    attempts_total = sum(p.attempts for p in progress.values())

    col1, col2, col3 = st.columns(3)
    col1.metric(t("dashboard.passed_count"), f"{passed} / {len(exercises)}")
    streak = study_streak(study_dates, date.today())
    col2.metric(t("dashboard.streak"), t("dashboard.streak_value", days=streak))
    col3.metric(t("dashboard.attempts_total"), t("dashboard.attempts_value", count=attempts_total))


def open_exercise(exercise_id: str) -> None:
    """演習ページの「選択中の問題」を書き換えてから移動する。"""
    st.session_state["current_exercise_id"] = exercise_id
    st.switch_page("pages/exercise.py")


def render_todo(
    exercises: list[Exercise],
    progress: dict[str, ExerciseProgress],
    reviews: dict[str, ReviewState],
) -> None:
    st.subheader(t("dashboard.todo"))
    recommendations = recommend(
        exercises, progress, reviews, date.today(), RECOMMEND_LIMIT, lang=t.lang
    )
    if not recommendations:
        st.success(t("dashboard.all_done"))
        return
    for item in recommendations:
        reason_col, title_col, button_col = st.columns([2, 5, 1], vertical_alignment="center")
        reason_col.write(item.reason)
        title_col.write(f"L{item.exercise.level} {item.exercise.title}")
        if button_col.button(t("dashboard.solve"), key=f"todo:{item.exercise.id}"):
            open_exercise(item.exercise.id)


def render_weak_topics(exercises: list[Exercise], progress: dict[str, ExerciseProgress]) -> None:
    st.subheader(t("dashboard.weak_topics"))
    weak = weak_topics(exercises, progress)
    if not weak:
        st.caption(t("dashboard.no_weak_topics"))
        return
    st.dataframe(
        [
            {
                t("dashboard.col.topic"): w.topic,
                t("dashboard.col.weak_score"): round(w.score, 1),
                t("dashboard.col.tried"): w.tried,
            }
            for w in weak
        ],
        hide_index=True,
    )
    st.caption(t("dashboard.weak_score_note"))


def render_topic_mastery(exercises: list[Exercise], progress: dict[str, ExerciseProgress]) -> None:
    st.subheader(t("dashboard.mastery"))
    mastery_col = t("dashboard.col.mastery")
    rows = [
        {
            t("dashboard.col.level"): row.level,
            t("dashboard.col.topic"): row.topic,
            t("dashboard.col.passed_total"): f"{row.passed} / {row.total}",
            mastery_col: row.ratio,
        }
        for row in topic_mastery(exercises, progress)
    ]
    st.dataframe(
        rows,
        hide_index=True,
        column_config={
            mastery_col: st.column_config.ProgressColumn(
                min_value=0.0, max_value=1.0, format="percent"
            )
        },
    )


def review_label(review: ReviewState | None) -> str:
    if review is None:
        return ""
    if review.completed:
        return t("dashboard.review_done")
    return t(
        "dashboard.review_next", number=review.next_review_number, date=f"{review.due_date:%m/%d}"
    )


def render_exercise_table(
    exercises: list[Exercise],
    progress: dict[str, ExerciseProgress],
    reviews: dict[str, ReviewState],
) -> None:
    st.subheader(t("dashboard.exercise_table"))
    rows = []
    for exercise in exercises:
        found = progress.get(exercise.id)
        status = status_of(exercise.id, progress)
        time_to_pass = found.time_to_pass if found else None
        rows.append(
            {
                t("dashboard.col.status"): f"{STATUS_ICONS[status]} {t(f'status.{status.name}')}",
                t("dashboard.col.level"): exercise.level,
                t("dashboard.col.exercise"): exercise.title,
                t("dashboard.col.attempts"): found.attempts if found else 0,
                t("dashboard.col.hints_used"): found.hints_used if found else 0,
                t("dashboard.col.solution_viewed"): "👀" if found and found.solution_viewed else "",
                t("dashboard.col.time_to_pass"): (
                    format_duration(time_to_pass, t.lang) if time_to_pass else ""
                ),
                t("dashboard.col.next_review"): review_label(reviews.get(exercise.id)),
            }
        )
    st.dataframe(rows, hide_index=True)
    st.caption(t("dashboard.table_note"))


def render_recent_attempts(exercises: list[Exercise], attempts: list[AttemptRecord]) -> None:
    st.subheader(t("dashboard.recent"))
    if not attempts:
        st.info(t("dashboard.no_history"))
        return
    titles = {ex.id: ex.title for ex in exercises}
    rows = [
        {
            t("dashboard.col.datetime"): attempt.attempted_at.astimezone().strftime(
                "%Y-%m-%d %H:%M"
            ),
            # 教材が削除・改名された場合は id のまま表示する
            t("dashboard.col.exercise"): titles.get(attempt.exercise_id, attempt.exercise_id),
            t("dashboard.col.result"): t(
                "dashboard.result_passed" if attempt.passed else "dashboard.result_failed"
            ),
            t("dashboard.col.error"): attempt.error_type or "",
            t("dashboard.col.duration_ms"): attempt.duration_ms,
        }
        for attempt in attempts
    ]
    st.dataframe(rows, hide_index=True)


def render_export(
    exercises: list[Exercise],
    progress: dict[str, ExerciseProgress],
    history: dict[str, list[AttemptRecord]],
    reviews: dict[str, ReviewState],
) -> None:
    st.subheader(t("dashboard.export"))
    stamp = f"{datetime.now():%Y%m%d}"
    csv_col, json_col = st.columns(2)
    csv_col.download_button(
        t("dashboard.export_csv"),
        data=attempts_to_csv(exercises, history),
        file_name=f"study-attempts-{stamp}.csv",
        mime="text/csv",
        width="stretch",
    )
    json_col.download_button(
        t("dashboard.export_json"),
        data=progress_to_json(exercises, progress, history, reviews, datetime.now()),
        file_name=f"study-progress-{stamp}.json",
        mime="application/json",
        width="stretch",
    )


def main() -> None:
    st.header(t("dashboard.title"))
    exercises = [ex.localized(t.lang) for ex in load_all().exercises]  # 問題名を表示言語に
    try:
        store = ProgressStore(db_path_from_env())
        progress = store.all_progress()
        study_dates = store.study_dates()
        attempts = store.recent_attempts(RECENT_LIMIT)
        history = store.attempt_history()
        reviews = review_states(history)
    except (sqlite3.Error, OSError):
        logger.exception("進捗DBの読み込みに失敗")
        st.error(t("dashboard.db_error"))
        return

    render_summary(exercises, progress, study_dates)
    render_todo(exercises, progress, reviews)
    render_weak_topics(exercises, progress)
    render_topic_mastery(exercises, progress)
    render_exercise_table(exercises, progress, reviews)
    render_recent_attempts(exercises, attempts)
    render_export(exercises, progress, history, reviews)


main()
