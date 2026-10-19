"""exercises/ 配下の教材(exercise.yaml + test_solution.py)を読み込む。

1問の定義が壊れていてもアプリ全体が落ちないよう、読み込みエラーは例外で止めずに
LoadResult.errors に集めて返す。
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from pydantic import ValidationError

from core.models import Exercise

logger = logging.getLogger(__name__)

EXERCISES_DIR = Path(__file__).resolve().parent.parent / "exercises"
EXERCISE_FILE = "exercise.yaml"
TEST_FILE = "test_solution.py"


class ExerciseLoadError(Exception):
    def __init__(self, path: Path, reason: str) -> None:
        super().__init__(f"{path}: {reason}")
        self.path = path
        self.reason = reason


@dataclass
class LoadResult:
    exercises: list[Exercise] = field(default_factory=list)
    errors: list[ExerciseLoadError] = field(default_factory=list)

    def by_id(self) -> dict[str, Exercise]:
        return {ex.id: ex for ex in self.exercises}


def load_exercise(directory: Path) -> Exercise:
    yaml_path = directory / EXERCISE_FILE
    try:
        raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as e:
        raise ExerciseLoadError(yaml_path, f"YAMLを読み込めません: {e}") from e
    if not isinstance(raw, dict):
        raise ExerciseLoadError(yaml_path, "YAMLのトップレベルはマッピングにしてください")

    test_path = directory / TEST_FILE
    if test_path.exists():
        raw["test_source"] = test_path.read_text(encoding="utf-8")

    try:
        exercise = Exercise.model_validate(raw)
    except ValidationError as e:
        raise ExerciseLoadError(yaml_path, f"定義が不正です:\n{e}") from e

    _check_location(exercise, directory, yaml_path)
    return exercise


def _check_location(exercise: Exercise, directory: Path, yaml_path: Path) -> None:
    """id・level・置き場所の食い違いを検出する(コピペで作った時のミス防止)。"""
    if not exercise.id.startswith(f"l{exercise.level}-"):
        raise ExerciseLoadError(yaml_path, f"id {exercise.id} が level {exercise.level} と不一致")
    if directory.parent.name != f"level{exercise.level}":
        raise ExerciseLoadError(yaml_path, f"level{exercise.level}/ 配下に置いてください")


def load_all(root: Path = EXERCISES_DIR) -> LoadResult:
    result = LoadResult()
    seen: dict[str, Path] = {}
    for yaml_path in sorted(root.glob(f"level*/*/{EXERCISE_FILE}")):
        try:
            exercise = load_exercise(yaml_path.parent)
        except ExerciseLoadError as e:
            logger.error("教材の読み込みに失敗: %s", e)
            result.errors.append(e)
            continue
        if exercise.id in seen:
            error = ExerciseLoadError(yaml_path, f"id {exercise.id} が {seen[exercise.id]} と重複")
            logger.error("%s", error)
            result.errors.append(error)
            continue
        seen[exercise.id] = yaml_path
        result.exercises.append(exercise)

    result.exercises.sort(key=lambda ex: (ex.level, ex.id))
    return result
