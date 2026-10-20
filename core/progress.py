"""学習の進捗を SQLite に保存・読み込みする。

テーブルは2つだけ:
- progress: 問題ごとの状態(取り組み開始日時・ヒント使用数・模範解答を見たか)
- attempts: 「実行」1回ごとの履歴(合否・エラー種別・実行時間)

挑戦回数や初合格日時は attempts から集計して求め、同じ情報を二重に持たない。
日時は UTC で保存し(文字列のまま正しく並び替えられる)、表示や日付の判定でローカル時刻に直す。

Streamlit は再実行のたびに別スレッドで動くことがあるため、接続は操作ごとに開いて閉じる。
"""

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from enum import StrEnum
from pathlib import Path

from core.models import GradeResult

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DB_PATH = PROJECT_ROOT / "data" / "app.db"
DB_PATH_ENV = "STUDY_APP_DB_PATH"

SCHEMA = """
CREATE TABLE IF NOT EXISTS progress (
    exercise_id     TEXT PRIMARY KEY,
    started_at      TEXT NOT NULL,
    hints_used      INTEGER NOT NULL DEFAULT 0,
    solution_viewed INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS attempts (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    exercise_id  TEXT NOT NULL REFERENCES progress (exercise_id),
    attempted_at TEXT NOT NULL,
    passed       INTEGER NOT NULL,
    error_type   TEXT,
    duration_ms  INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_attempts_exercise ON attempts (exercise_id);
"""


class Status(StrEnum):
    NOT_STARTED = "未着手"
    IN_PROGRESS = "挑戦中"
    PASSED = "合格"


@dataclass(frozen=True)
class ExerciseProgress:
    exercise_id: str
    started_at: datetime
    attempts: int = 0
    failures: int = 0
    hints_used: int = 0
    solution_viewed: bool = False
    first_passed_at: datetime | None = None

    @property
    def status(self) -> Status:
        if self.first_passed_at is not None:
            return Status.PASSED
        if self.attempts > 0:
            return Status.IN_PROGRESS
        return Status.NOT_STARTED  # 開いただけで、まだ実行していない

    @property
    def time_to_pass(self) -> timedelta | None:
        """初めて問題を開いてから初合格までの時間。"""
        if self.first_passed_at is None:
            return None
        return self.first_passed_at - self.started_at


@dataclass(frozen=True)
class AttemptRecord:
    exercise_id: str
    attempted_at: datetime
    passed: bool
    error_type: str | None
    duration_ms: int


def now_utc() -> datetime:
    return datetime.now(UTC)


def db_path_from_env() -> Path:
    """環境変数 STUDY_APP_DB_PATH(相対パスはプロジェクト直下から)か、既定の data/app.db。"""
    value = os.environ.get(DB_PATH_ENV, "").strip()
    if not value:
        return DEFAULT_DB_PATH
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


class ProgressStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """接続を開き、成功ならコミット・失敗ならロールバックして、必ず閉じる。

        (sqlite3.connect の with 文はコミットするだけで接続を閉じないので、自前で用意する)
        """
        conn = sqlite3.connect(self.path)
        conn.row_factory = sqlite3.Row  # 列名で値を取り出せるようにする
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    # --- 書き込み -------------------------------------------------------------

    def start(self, exercise_id: str, now: datetime | None = None) -> None:
        """問題を初めて開いた日時を記録する(2回目以降は何もしない)。"""
        with self._connect() as conn:
            self._ensure_started(conn, exercise_id, now or now_utc())

    def record_attempt(
        self, exercise_id: str, result: GradeResult, now: datetime | None = None
    ) -> None:
        now = now or now_utc()
        with self._connect() as conn:
            self._ensure_started(conn, exercise_id, now)
            conn.execute(
                "INSERT INTO attempts (exercise_id, attempted_at, passed, error_type, duration_ms)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    exercise_id,
                    now.isoformat(),
                    result.passed,
                    result.error_type,
                    result.duration_ms,
                ),
            )

    def record_hints(self, exercise_id: str, hints_shown: int, now: datetime | None = None) -> None:
        """ヒントの開示数を記録する。減ることはないので大きい方を残す。"""
        with self._connect() as conn:
            self._ensure_started(conn, exercise_id, now or now_utc())
            conn.execute(
                "UPDATE progress SET hints_used = MAX(hints_used, ?) WHERE exercise_id = ?",
                (hints_shown, exercise_id),
            )

    def record_solution_viewed(self, exercise_id: str, now: datetime | None = None) -> None:
        with self._connect() as conn:
            self._ensure_started(conn, exercise_id, now or now_utc())
            conn.execute(
                "UPDATE progress SET solution_viewed = 1 WHERE exercise_id = ?", (exercise_id,)
            )

    @staticmethod
    def _ensure_started(conn: sqlite3.Connection, exercise_id: str, now: datetime) -> None:
        conn.execute(
            "INSERT OR IGNORE INTO progress (exercise_id, started_at) VALUES (?, ?)",
            (exercise_id, now.isoformat()),
        )

    # --- 読み込み -------------------------------------------------------------

    # 問題ごとの状態に、attempts から集計した挑戦回数と初合格日時を付け加える
    _PROGRESS_QUERY = """
        SELECT p.exercise_id, p.started_at, p.hints_used, p.solution_viewed,
               COUNT(a.id) AS attempts,
               COUNT(a.id) - COALESCE(SUM(a.passed), 0) AS failures,
               MIN(CASE WHEN a.passed THEN a.attempted_at END) AS first_passed_at
        FROM progress AS p
        LEFT JOIN attempts AS a ON a.exercise_id = p.exercise_id
    """

    def get(self, exercise_id: str) -> ExerciseProgress | None:
        with self._connect() as conn:
            row = conn.execute(
                f"{self._PROGRESS_QUERY} WHERE p.exercise_id = ? GROUP BY p.exercise_id",
                (exercise_id,),
            ).fetchone()
        return _to_progress(row) if row else None

    def all_progress(self) -> dict[str, ExerciseProgress]:
        with self._connect() as conn:
            rows = conn.execute(f"{self._PROGRESS_QUERY} GROUP BY p.exercise_id").fetchall()
        return {row["exercise_id"]: _to_progress(row) for row in rows}

    _ATTEMPT_COLUMNS = "exercise_id, attempted_at, passed, error_type, duration_ms"

    def recent_attempts(self, limit: int = 10) -> list[AttemptRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT {self._ATTEMPT_COLUMNS} FROM attempts ORDER BY id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [_to_attempt(row) for row in rows]

    def attempt_history(self) -> dict[str, list[AttemptRecord]]:
        """問題ごとの全挑戦履歴(古い順)。復習の時期の計算に使う。"""
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT {self._ATTEMPT_COLUMNS} FROM attempts ORDER BY id"
            ).fetchall()
        history: dict[str, list[AttemptRecord]] = {}
        for row in rows:
            history.setdefault(row["exercise_id"], []).append(_to_attempt(row))
        return history

    def study_dates(self) -> set[date]:
        """1回以上「実行」した日(ローカル時刻の日付)の集合。"""
        with self._connect() as conn:
            rows = conn.execute("SELECT attempted_at FROM attempts").fetchall()
        return {datetime.fromisoformat(row["attempted_at"]).astimezone().date() for row in rows}


def _to_progress(row: sqlite3.Row) -> ExerciseProgress:
    first_passed = row["first_passed_at"]
    return ExerciseProgress(
        exercise_id=row["exercise_id"],
        started_at=datetime.fromisoformat(row["started_at"]),
        attempts=row["attempts"],
        failures=row["failures"],
        hints_used=row["hints_used"],
        solution_viewed=bool(row["solution_viewed"]),
        first_passed_at=datetime.fromisoformat(first_passed) if first_passed else None,
    )


def _to_attempt(row: sqlite3.Row) -> AttemptRecord:
    return AttemptRecord(
        exercise_id=row["exercise_id"],
        attempted_at=datetime.fromisoformat(row["attempted_at"]),
        passed=bool(row["passed"]),
        error_type=row["error_type"],
        duration_ms=row["duration_ms"],
    )
