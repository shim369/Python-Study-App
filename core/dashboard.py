"""ダッシュボードに表示する集計(連続学習日数・トピック別習熟度など)。

DB にも Streamlit にも依存しない純粋な計算だけを置き、単体テストしやすくしている。
"""

from dataclasses import dataclass
from datetime import date, timedelta

from core.i18n import DEFAULT_LANG, Lang, Translator
from core.models import Exercise
from core.progress import ExerciseProgress, Status


def study_streak(study_dates: set[date], today: date) -> int:
    """今日(まだ今日やっていなければ昨日)から遡って、毎日学習した日数。

    今日まだ学習していないだけで連続記録が 0 に見えないよう、昨日までの連続も数える。
    """
    day = today if today in study_dates else today - timedelta(days=1)
    streak = 0
    while day in study_dates:
        streak += 1
        day -= timedelta(days=1)
    return streak


def status_of(exercise_id: str, progress: dict[str, ExerciseProgress]) -> Status:
    found = progress.get(exercise_id)
    return found.status if found else Status.NOT_STARTED


@dataclass(frozen=True)
class TopicMastery:
    level: int
    topic: str
    passed: int
    total: int

    @property
    def ratio(self) -> float:
        return self.passed / self.total if self.total else 0.0


def topic_mastery(
    exercises: list[Exercise], progress: dict[str, ExerciseProgress]
) -> list[TopicMastery]:
    """トピックごとの「合格した問題数 / 問題数」。レベル → トピック名の順に並べる。"""
    totals: dict[str, int] = {}
    passed: dict[str, int] = {}
    levels: dict[str, int] = {}
    for exercise in exercises:
        topic = exercise.topic
        totals[topic] = totals.get(topic, 0) + 1
        passed.setdefault(topic, 0)
        if status_of(exercise.id, progress) is Status.PASSED:
            passed[topic] += 1
        # 複数レベルにまたがるトピックは、一番低いレベルに並べる
        levels[topic] = min(levels.get(topic, exercise.level), exercise.level)

    rows = [TopicMastery(levels[t], t, passed[t], totals[t]) for t in totals]
    return sorted(rows, key=lambda row: (row.level, row.topic))


def format_duration(duration: timedelta, lang: Lang = DEFAULT_LANG) -> str:
    """「45秒」「12分」「3時間5分」「2日4時間」のように大まかな長さで表す。"""
    t = Translator(lang)
    seconds = int(duration.total_seconds())
    if seconds < 60:
        return t("duration.seconds", seconds=max(seconds, 0))
    minutes, _ = divmod(seconds, 60)
    if minutes < 60:
        return t("duration.minutes", minutes=minutes)
    hours, minutes = divmod(minutes, 60)
    if hours < 24:
        if minutes:
            return t("duration.hours_minutes", hours=hours, minutes=minutes)
        return t("duration.hours", hours=hours)
    days, hours = divmod(hours, 24)
    return (
        t("duration.days_hours", days=days, hours=hours) if hours else t("duration.days", days=days)
    )
