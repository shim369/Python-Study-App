"""ダッシュボード: 全体の進み具合・トピック別習熟度・問題ごとの状態・直近の学習履歴。

集計は core/dashboard.py、データの読み込みは core/progress.py が担当し、ここは表示だけ。
"""

import logging
import sqlite3
from datetime import date

import streamlit as st

from core.dashboard import format_duration, status_of, study_streak, topic_mastery
from core.loader import load_all
from core.models import Exercise
from core.progress import AttemptRecord, ExerciseProgress, ProgressStore, Status, db_path_from_env

logger = logging.getLogger(__name__)

RECENT_LIMIT = 15
STATUS_ICONS = {Status.NOT_STARTED: "⬜", Status.IN_PROGRESS: "✏️", Status.PASSED: "✅"}


def render_summary(
    exercises: list[Exercise], progress: dict[str, ExerciseProgress], study_dates: set[date]
) -> None:
    passed = sum(status_of(ex.id, progress) is Status.PASSED for ex in exercises)
    attempts_total = sum(p.attempts for p in progress.values())

    col1, col2, col3 = st.columns(3)
    col1.metric("合格した問題", f"{passed} / {len(exercises)}")
    col2.metric("連続学習日数", f"{study_streak(study_dates, date.today())} 日")
    col3.metric("総挑戦回数", f"{attempts_total} 回")


def render_topic_mastery(exercises: list[Exercise], progress: dict[str, ExerciseProgress]) -> None:
    st.subheader("トピック別習熟度")
    rows = [
        {
            "レベル": row.level,
            "トピック": row.topic,
            "合格 / 問題数": f"{row.passed} / {row.total}",
            "習熟度": row.ratio,
        }
        for row in topic_mastery(exercises, progress)
    ]
    st.dataframe(
        rows,
        hide_index=True,
        column_config={
            "習熟度": st.column_config.ProgressColumn(
                min_value=0.0, max_value=1.0, format="percent"
            )
        },
    )


def render_exercise_table(exercises: list[Exercise], progress: dict[str, ExerciseProgress]) -> None:
    st.subheader("問題ごとの状態")
    rows = []
    for exercise in exercises:
        found = progress.get(exercise.id)
        status = status_of(exercise.id, progress)
        time_to_pass = found.time_to_pass if found else None
        rows.append(
            {
                "状態": f"{STATUS_ICONS[status]} {status}",
                "レベル": exercise.level,
                "問題": exercise.title,
                "挑戦回数": found.attempts if found else 0,
                "ヒント使用": found.hints_used if found else 0,
                "模範解答を見た": "👀" if found and found.solution_viewed else "",
                "合格までの時間": format_duration(time_to_pass) if time_to_pass else "",
            }
        )
    st.dataframe(rows, hide_index=True)
    st.caption("合格までの時間 = 問題を初めて開いてから、初めて合格するまで")


def render_recent_attempts(exercises: list[Exercise], attempts: list[AttemptRecord]) -> None:
    st.subheader("直近の学習履歴")
    if not attempts:
        st.info("まだ履歴がありません。「演習」ページで問題を解いてみましょう。")
        return
    titles = {ex.id: ex.title for ex in exercises}
    rows = [
        {
            "日時": attempt.attempted_at.astimezone().strftime("%Y-%m-%d %H:%M"),
            # 教材が削除・改名された場合は id のまま表示する
            "問題": titles.get(attempt.exercise_id, attempt.exercise_id),
            "結果": "✅ 合格" if attempt.passed else "❌ 不合格",
            "エラー": attempt.error_type or "",
            "実行時間(ms)": attempt.duration_ms,
        }
        for attempt in attempts
    ]
    st.dataframe(rows, hide_index=True)


def main() -> None:
    st.title("ダッシュボード")
    exercises = load_all().exercises
    try:
        store = ProgressStore(db_path_from_env())
        progress = store.all_progress()
        study_dates = store.study_dates()
        attempts = store.recent_attempts(RECENT_LIMIT)
    except (sqlite3.Error, OSError):
        logger.exception("進捗DBの読み込みに失敗")
        st.error("進捗DBを読み込めませんでした。ターミナルのログを確認してください。")
        return

    render_summary(exercises, progress, study_dates)
    render_topic_mastery(exercises, progress)
    render_exercise_table(exercises, progress)
    render_recent_attempts(exercises, attempts)


main()
