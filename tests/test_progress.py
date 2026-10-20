from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from core.models import GradeResult
from core.progress import (
    DEFAULT_DB_PATH,
    PROJECT_ROOT,
    ProgressStore,
    Status,
    db_path_from_env,
)

T0 = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)
PASSED = GradeResult(passed=True, duration_ms=120)
FAILED = GradeResult(passed=False, duration_ms=80, error_type="AssertionError")


@pytest.fixture
def store(tmp_path: Path) -> ProgressStore:
    return ProgressStore(tmp_path / "sub" / "app.db")  # 親ディレクトリも作られる


def test_unknown_exercise_has_no_progress(store: ProgressStore) -> None:
    assert store.get("l1-001-x") is None
    assert store.all_progress() == {}


def test_opened_but_not_run_is_not_started(store: ProgressStore) -> None:
    store.start("l1-001-x", now=T0)
    progress = store.get("l1-001-x")
    assert progress is not None
    assert progress.status is Status.NOT_STARTED
    assert progress.started_at == T0


def test_start_keeps_first_opened_time(store: ProgressStore) -> None:
    store.start("l1-001-x", now=T0)
    store.start("l1-001-x", now=T0 + timedelta(days=1))
    progress = store.get("l1-001-x")
    assert progress is not None
    assert progress.started_at == T0


def test_attempts_are_counted_and_first_pass_is_kept(store: ProgressStore) -> None:
    store.start("l1-001-x", now=T0)
    store.record_attempt("l1-001-x", FAILED, now=T0 + timedelta(minutes=5))
    progress = store.get("l1-001-x")
    assert progress is not None
    assert progress.status is Status.IN_PROGRESS

    store.record_attempt("l1-001-x", PASSED, now=T0 + timedelta(minutes=12))
    store.record_attempt("l1-001-x", FAILED, now=T0 + timedelta(minutes=20))
    progress = store.get("l1-001-x")
    assert progress is not None
    assert progress.attempts == 3
    assert progress.status is Status.PASSED  # 合格後に失敗しても合格のまま
    assert progress.time_to_pass == timedelta(minutes=12)


def test_attempt_without_start_starts_the_exercise(store: ProgressStore) -> None:
    store.record_attempt("l1-001-x", PASSED, now=T0)
    progress = store.get("l1-001-x")
    assert progress is not None
    assert progress.time_to_pass == timedelta(0)


def test_hints_used_never_decreases(store: ProgressStore) -> None:
    store.record_hints("l1-001-x", 2, now=T0)
    store.record_hints("l1-001-x", 1, now=T0)
    progress = store.get("l1-001-x")
    assert progress is not None
    assert progress.hints_used == 2


def test_solution_viewed(store: ProgressStore) -> None:
    store.record_solution_viewed("l1-001-x", now=T0)
    progress = store.get("l1-001-x")
    assert progress is not None
    assert progress.solution_viewed


def test_data_survives_reopening(tmp_path: Path) -> None:
    path = tmp_path / "app.db"
    ProgressStore(path).record_attempt("l1-001-x", PASSED, now=T0)
    reopened = ProgressStore(path)  # アプリ再起動に相当
    assert reopened.all_progress()["l1-001-x"].status is Status.PASSED


def test_recent_attempts_are_newest_first(store: ProgressStore) -> None:
    store.record_attempt("l1-001-x", FAILED, now=T0)
    store.record_attempt("l1-002-y", PASSED, now=T0 + timedelta(minutes=1))
    store.record_attempt("l1-001-x", PASSED, now=T0 + timedelta(minutes=2))

    recent = store.recent_attempts(limit=2)
    assert [(a.exercise_id, a.passed) for a in recent] == [("l1-001-x", True), ("l1-002-y", True)]
    oldest = store.recent_attempts()[-1]
    assert oldest.error_type == "AssertionError"
    assert oldest.duration_ms == 80
    assert oldest.attempted_at == T0


def test_study_dates_are_local_dates(store: ProgressStore) -> None:
    store.record_attempt("l1-001-x", PASSED, now=T0)
    store.record_attempt("l1-001-x", PASSED, now=T0 + timedelta(hours=1))
    store.record_attempt("l1-001-x", PASSED, now=T0 + timedelta(days=2))
    assert store.study_dates() == {
        T0.astimezone().date(),
        (T0 + timedelta(days=2)).astimezone().date(),
    }


def test_db_path_defaults_to_data_dir(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STUDY_APP_DB_PATH", raising=False)
    assert db_path_from_env() == DEFAULT_DB_PATH


def test_db_path_relative_to_project_root(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STUDY_APP_DB_PATH", "data/other.db")
    assert db_path_from_env() == PROJECT_ROOT / "data" / "other.db"


def test_db_path_absolute(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("STUDY_APP_DB_PATH", str(tmp_path / "x.db"))
    assert db_path_from_env() == tmp_path / "x.db"


def test_failures_are_counted(store: ProgressStore) -> None:
    store.record_attempt("l1-001-x", FAILED, now=T0)
    store.record_attempt("l1-001-x", FAILED, now=T0)
    store.record_attempt("l1-001-x", PASSED, now=T0)
    store.start("l1-002-y", now=T0)
    progress = store.all_progress()
    assert progress["l1-001-x"].failures == 2
    assert progress["l1-002-y"].failures == 0  # 挑戦なしでも 0(NULL にならない)


def test_attempt_history_is_grouped_and_oldest_first(store: ProgressStore) -> None:
    store.record_attempt("l1-001-x", FAILED, now=T0)
    store.record_attempt("l1-002-y", PASSED, now=T0 + timedelta(minutes=1))
    store.record_attempt("l1-001-x", PASSED, now=T0 + timedelta(minutes=2))
    history = store.attempt_history()
    assert [a.passed for a in history["l1-001-x"]] == [False, True]
    assert [a.passed for a in history["l1-002-y"]] == [True]
