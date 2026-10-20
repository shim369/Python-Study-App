"""ファイルを探す(pathlib)のテスト。学習者のコードは solution.py として配置される。"""

from pathlib import Path

import pytest

from solution import find_files


def make_file(root: Path, relative: str, size: int = 0) -> None:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"x" * size)


@pytest.fixture
def root(tmp_path: Path) -> Path:
    make_file(tmp_path, "a.txt", 10)
    make_file(tmp_path, "b.md", 5)
    make_file(tmp_path, "docs/c.TXT", 0)
    make_file(tmp_path, "docs/deep/d.txt", 100)
    make_file(tmp_path, "docs/deep/archive.tar.gz", 50)
    make_file(tmp_path, "docs/readme", 20)  # 拡張子なし
    (tmp_path / "notes.txt").mkdir()  # .txt という名前のディレクトリ
    return tmp_path


def test_example_from_description(root: Path) -> None:
    assert find_files(root, ".txt") == ["a.txt", "docs/c.TXT", "docs/deep/d.txt"]


@pytest.mark.parametrize(
    ("suffix", "min_bytes", "expected"),
    [
        (".txt", 1, ["a.txt", "docs/deep/d.txt"]),
        (".txt", 10, ["a.txt", "docs/deep/d.txt"]),  # ちょうど min_bytes は含む
        (".txt", 11, ["docs/deep/d.txt"]),
        (".TXT", 0, ["a.txt", "docs/c.TXT", "docs/deep/d.txt"]),  # suffix 側の大文字小文字
        (".gz", 0, ["docs/deep/archive.tar.gz"]),  # 最後の拡張子
        (".md", 0, ["b.md"]),
        (".py", 0, []),  # 該当なし
    ],
)
def test_conditions(root: Path, suffix: str, min_bytes: int, expected: list[str]) -> None:
    assert find_files(root, suffix, min_bytes) == expected


def test_empty_directory(tmp_path: Path) -> None:
    assert find_files(tmp_path, ".txt") == []
