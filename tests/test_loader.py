from pathlib import Path

import pytest

from core.loader import ExerciseLoadError, load_all, load_exercise

VALID_YAML = """
id: l1-001-double
title: 2倍
level: 1
topic: function
description: 2倍にする
starter_code: |
  def double(n): ...
grading: pytest
hints: [a, b, c]
solution: |
  def double(n): return n * 2
"""
TESTS = "from solution import double\n\ndef test_double():\n    assert double(2) == 4\n"


def write_exercise(
    root: Path, level_dir: str, name: str, yaml_text: str, tests: str | None
) -> Path:
    directory = root / level_dir / name
    directory.mkdir(parents=True)
    (directory / "exercise.yaml").write_text(yaml_text, encoding="utf-8")
    if tests is not None:
        (directory / "test_solution.py").write_text(tests, encoding="utf-8")
    return directory


def test_load_exercise_reads_tests(tmp_path: Path) -> None:
    directory = write_exercise(tmp_path, "level1", "001_double", VALID_YAML, TESTS)
    exercise = load_exercise(directory)
    assert exercise.id == "l1-001-double"
    assert exercise.test_source == TESTS
    assert exercise.level_name == "基礎"


def test_missing_test_file_is_error(tmp_path: Path) -> None:
    directory = write_exercise(tmp_path, "level1", "001_double", VALID_YAML, None)
    with pytest.raises(ExerciseLoadError, match=r"test_solution\.py"):
        load_exercise(directory)


def test_invalid_yaml_is_error(tmp_path: Path) -> None:
    directory = write_exercise(tmp_path, "level1", "001_x", "id: [unclosed", TESTS)
    with pytest.raises(ExerciseLoadError, match="YAML"):
        load_exercise(directory)


def test_non_mapping_yaml_is_error(tmp_path: Path) -> None:
    directory = write_exercise(tmp_path, "level1", "001_x", "- a\n- b\n", TESTS)
    with pytest.raises(ExerciseLoadError, match="マッピング"):
        load_exercise(directory)


def test_level_and_directory_mismatch(tmp_path: Path) -> None:
    directory = write_exercise(tmp_path, "level2", "001_double", VALID_YAML, TESTS)
    with pytest.raises(ExerciseLoadError, match="level1/"):
        load_exercise(directory)


def test_id_and_level_mismatch(tmp_path: Path) -> None:
    yaml_text = VALID_YAML.replace("level: 1", "level: 2")
    directory = write_exercise(tmp_path, "level2", "001_double", yaml_text, TESTS)
    with pytest.raises(ExerciseLoadError, match="不一致"):
        load_exercise(directory)


def test_load_all_collects_errors_and_duplicates(tmp_path: Path) -> None:
    write_exercise(tmp_path, "level1", "001_double", VALID_YAML, TESTS)
    write_exercise(tmp_path, "level1", "002_dup", VALID_YAML, TESTS)  # 同じ id
    write_exercise(tmp_path, "level1", "003_broken", "id: [", TESTS)
    result = load_all(tmp_path)
    assert [ex.id for ex in result.exercises] == ["l1-001-double"]
    assert len(result.errors) == 2
    assert any("重複" in e.reason for e in result.errors)
    assert set(result.by_id()) == {"l1-001-double"}
