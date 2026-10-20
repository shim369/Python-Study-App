"""行数・単語数を数えるCLI のテスト。学習者のコードは solution.py として配置される。"""

from pathlib import Path

import pytest

from solution import main


@pytest.fixture(autouse=True)
def files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)  # ファイル名を相対パスで渡せるようにする
    Path("a.txt").write_text(
        "hello world\nこんにちは 世界 です\n\nlast line here", encoding="utf-8"
    )
    Path("b.txt").write_text("one two", encoding="utf-8")
    Path("empty.txt").write_text("", encoding="utf-8")


@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (["a.txt"], "4 8 a.txt\n"),
        (["-l", "a.txt"], "4 a.txt\n"),
        (["--words", "a.txt"], "8 a.txt\n"),
        (["-l", "-w", "a.txt"], "4 8 a.txt\n"),  # 両方指定 = 両方表示
        (["a.txt", "b.txt"], "4 8 a.txt\n1 2 b.txt\n"),  # 複数ファイル
        (["empty.txt"], "0 0 empty.txt\n"),
    ],
)
def test_output(argv: list[str], expected: str, capsys: pytest.CaptureFixture[str]) -> None:
    assert main(argv) == 0
    captured = capsys.readouterr()
    assert captured.out == expected
    assert captured.err == ""


def test_missing_file_continues_and_returns_1(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["nope.txt", "b.txt"]) == 1
    captured = capsys.readouterr()
    assert captured.out == "1 2 b.txt\n"
    assert captured.err.strip() == "error: ファイルが見つかりません: nope.txt"


@pytest.mark.parametrize("argv", [[], ["--unknown", "a.txt"]])
def test_argparse_errors(argv: list[str]) -> None:
    with pytest.raises(SystemExit) as info:
        main(argv)
    assert info.value.code == 2  # argparse のエラーは終了コード 2


def test_help(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as info:
        main(["--help"])
    assert info.value.code == 0
    out = capsys.readouterr().out
    assert "--lines" in out
    assert "--words" in out
