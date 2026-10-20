"""環境変数を一時的に変える のテスト。学習者のコードは solution.py として配置される。"""

import os
from collections.abc import Iterator

import pytest

from solution import override_env

KEYS = ("STUDY_A", "STUDY_B", "STUDY_C")


@pytest.fixture(autouse=True)
def clean_env() -> Iterator[None]:
    for key in KEYS:
        os.environ.pop(key, None)
    yield
    for key in KEYS:
        os.environ.pop(key, None)


def test_sets_and_restores_existing_value() -> None:
    os.environ["STUDY_A"] = "original"
    with override_env(STUDY_A="temp"):
        assert os.environ["STUDY_A"] == "temp"
    assert os.environ["STUDY_A"] == "original"


def test_new_key_is_removed_after_block() -> None:
    with override_env(STUDY_A="temp"):
        assert os.environ["STUDY_A"] == "temp"
    assert "STUDY_A" not in os.environ


def test_none_deletes_and_restores() -> None:
    os.environ["STUDY_A"] = "original"
    with override_env(STUDY_A=None, STUDY_B=None):  # STUDY_B は元から無い
        assert "STUDY_A" not in os.environ
        assert "STUDY_B" not in os.environ
    assert os.environ["STUDY_A"] == "original"
    assert "STUDY_B" not in os.environ


def test_restores_on_exception() -> None:
    os.environ["STUDY_A"] = "original"
    with pytest.raises(RuntimeError, match="boom"), override_env(STUDY_A="x", STUDY_B="y"):
        raise RuntimeError("boom")
    assert os.environ["STUDY_A"] == "original"
    assert "STUDY_B" not in os.environ


def test_other_keys_are_untouched() -> None:
    os.environ["STUDY_C"] = "keep"
    with override_env(STUDY_A="x"):
        os.environ["STUDY_C"] = "changed inside"
    assert os.environ["STUDY_C"] == "changed inside"  # 指定していないキーは戻さない


def test_nested_blocks() -> None:
    with override_env(STUDY_A="outer"):
        with override_env(STUDY_A="inner"):
            assert os.environ["STUDY_A"] == "inner"
        assert os.environ["STUDY_A"] == "outer"
    assert "STUDY_A" not in os.environ
