"""簡易的な間隔反復(Spaced Repetition)。合格した問題を、間隔を空けて再出題する。

ルール(固定間隔):
- 初めて合格した日の 1日後 → 3日後 → 7日後 に復習する。3回とも合格したら「復習完了」
- 期限日以降に合格すると、その回の復習が済み、次の間隔の期限が決まる
- 期限前の合格は数えない(間隔を空けることに意味があるため)
- 期限日以降に不合格になったら、合格した時点から「1日後」の間隔でやり直す

挑戦履歴(AttemptRecord のリスト)だけから計算するので、DB に復習用の列は持たない。
日付はローカル時刻の日付で比べる(夜に合格しても、翌朝には「1日後」として出題される)。
"""

from dataclasses import dataclass
from datetime import date, timedelta

from core.progress import AttemptRecord

REVIEW_INTERVALS: tuple[timedelta, ...] = (
    timedelta(days=1),
    timedelta(days=3),
    timedelta(days=7),
)


@dataclass(frozen=True)
class ReviewState:
    reviews_done: int  # 済んだ復習の回数(0〜len(REVIEW_INTERVALS))
    due_date: date | None  # 次の復習の期限日。None なら復習完了

    @property
    def completed(self) -> bool:
        return self.due_date is None

    @property
    def next_review_number(self) -> int:
        """次が何回目の復習か(1始まり)。表示用。"""
        return self.reviews_done + 1

    def is_due(self, today: date) -> bool:
        return self.due_date is not None and today >= self.due_date


def _local_date(attempt: AttemptRecord) -> date:
    return attempt.attempted_at.astimezone().date()


def review_state(attempts: list[AttemptRecord]) -> ReviewState | None:
    """1問分の挑戦履歴(古い順)から復習の状態を求める。まだ合格していなければ None。"""
    reviews_done = 0
    due_date: date | None = None
    has_passed = False
    lapsed = False  # 復習で失敗し、間隔をやり直す状態

    for attempt in attempts:
        day = _local_date(attempt)
        if not has_passed:
            if attempt.passed:
                has_passed = True
                due_date = day + REVIEW_INTERVALS[0]
            continue
        if due_date is None or day < due_date:
            continue  # 復習完了後や期限前の挑戦は、復習の進み具合に影響しない
        if not attempt.passed:
            lapsed = True
        elif lapsed:
            reviews_done, lapsed = 0, False
            due_date = day + REVIEW_INTERVALS[0]
        else:
            reviews_done += 1
            has_next = reviews_done < len(REVIEW_INTERVALS)
            due_date = day + REVIEW_INTERVALS[reviews_done] if has_next else None

    return ReviewState(reviews_done, due_date) if has_passed else None


def review_states(history: dict[str, list[AttemptRecord]]) -> dict[str, ReviewState]:
    """全問題の復習状態。合格したことのある問題だけが入る。"""
    states = {exercise_id: review_state(attempts) for exercise_id, attempts in history.items()}
    return {exercise_id: state for exercise_id, state in states.items() if state is not None}
