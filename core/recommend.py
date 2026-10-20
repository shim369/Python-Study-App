"""苦手トピックの判定と、「次に解くべき問題」のおすすめ。

苦手度(1問あたり) = 不合格の回数 + 使ったヒントの数 + 模範解答を見たら 3
トピックの苦手度は、そのトピックで挑戦した問題の苦手度の平均。
(AI ヒントは数えない。DB に保存している教材のヒントだけで判定する)
"""

from dataclasses import dataclass
from datetime import date

from core.dashboard import status_of
from core.models import Exercise
from core.progress import ExerciseProgress, Status
from core.srs import ReviewState

SOLUTION_VIEWED_PENALTY = 3
WEAK_THRESHOLD = 3.0


def struggle_score(progress: ExerciseProgress) -> int:
    """1問でどれだけ苦労したか。大きいほど苦手。"""
    penalty = SOLUTION_VIEWED_PENALTY if progress.solution_viewed else 0
    return progress.failures + progress.hints_used + penalty


@dataclass(frozen=True)
class TopicWeakness:
    topic: str
    score: float  # 挑戦した問題の苦手度の平均
    tried: int  # 挑戦した問題数


def weak_topics(
    exercises: list[Exercise],
    progress: dict[str, ExerciseProgress],
    threshold: float = WEAK_THRESHOLD,
) -> list[TopicWeakness]:
    """苦手度が threshold 以上のトピックを、苦手な順に返す。"""
    scores: dict[str, list[int]] = {}
    for exercise in exercises:
        found = progress.get(exercise.id)
        if found and found.attempts > 0:
            scores.setdefault(exercise.topic, []).append(struggle_score(found))

    weak = [
        TopicWeakness(topic, sum(values) / len(values), len(values))
        for topic, values in scores.items()
        if sum(values) / len(values) >= threshold
    ]
    return sorted(weak, key=lambda w: w.score, reverse=True)


@dataclass(frozen=True)
class Recommendation:
    exercise: Exercise
    reason: str


def recommend(
    exercises: list[Exercise],
    progress: dict[str, ExerciseProgress],
    reviews: dict[str, ReviewState],
    today: date,
    limit: int = 5,
) -> list[Recommendation]:
    """次に解くべき問題を、優先度の高い順に最大 limit 件返す。

    優先度: 1. 復習の期限が来た問題(期限が古い順)
            2. 挑戦中(まだ合格していない)の問題
            3. 苦手トピックの未着手の問題
            4. 未着手の問題(レベルの低い順 = カリキュラム順)
    """
    exercises = sorted(exercises, key=lambda ex: (ex.level, ex.id))

    due = sorted(
        (ex for ex in exercises if ex.id in reviews and reviews[ex.id].is_due(today)),
        key=lambda ex: reviews[ex.id].due_date or today,
    )
    in_progress = [ex for ex in exercises if status_of(ex.id, progress) is Status.IN_PROGRESS]
    not_started = [ex for ex in exercises if status_of(ex.id, progress) is Status.NOT_STARTED]
    weak = {w.topic for w in weak_topics(exercises, progress)}

    candidates = [
        *(Recommendation(ex, f"🔁 復習({reviews[ex.id].next_review_number}回目)") for ex in due),
        *(Recommendation(ex, "✏️ 挑戦中") for ex in in_progress),
        *(
            Recommendation(ex, f"💪 苦手トピック「{ex.topic}」")
            for ex in not_started
            if ex.topic in weak
        ),
        *(Recommendation(ex, "🆕 次の問題") for ex in not_started if ex.topic not in weak),
    ]
    return candidates[:limit]
