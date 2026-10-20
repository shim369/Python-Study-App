"""全演習(または指定した演習)の模範解答を検証する。

使い方:
    uv run python scripts/verify_solutions.py            # 全問を検証
    uv run python scripts/verify_solutions.py --id l1-001-word-frequency
    uv run python scripts/verify_solutions.py --level 2
    uv run python scripts/verify_solutions.py --list     # 既存演習の一覧(重複確認用)
    uv run python scripts/verify_solutions.py --id <id> --try cheat.py
        # 任意のコードで採点する(ハードコードした「ずるい解答」が落ちるかの確認用)

終了コード: 全問OKなら 0、1問でも問題があれば 1
"""

import argparse
import sys
from pathlib import Path

from core.grading import grade
from core.loader import load_all
from core.models import Exercise
from core.verify import verify_exercise


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").strip().splitlines()[0])
    parser.add_argument("--id", help="この id の演習だけ検証する")
    parser.add_argument("--level", type=int, help="このレベルの演習だけ検証する")
    parser.add_argument("--list", action="store_true", help="検証せずに一覧を表示する")
    parser.add_argument(
        "--try", dest="try_file", type=Path, help="--id の演習を、このファイルのコードで採点する"
    )
    args = parser.parse_args()

    loaded = load_all()
    for error in loaded.errors:
        print(f"❌ 読み込みエラー {error}")

    exercises = loaded.exercises
    if args.id:
        exercises = [ex for ex in exercises if ex.id == args.id]
        if not exercises:
            print(f"❌ id {args.id} の演習が見つかりません")
            return 1
    if args.try_file:
        if not args.id:
            print("❌ --try には --id も指定してください")
            return 1
        return try_code(exercises[0], args.try_file)
    if args.level:
        exercises = [ex for ex in exercises if ex.level == args.level]

    if args.list:
        for ex in exercises:
            tags = ",".join(ex.tags)
            print(f"{ex.id}\t{ex.title}\ttopic={ex.topic}\tkind={ex.kind}\ttags={tags}")
        return 0

    failures = len(loaded.errors)
    for ex in exercises:
        report = verify_exercise(ex)
        if report.ok:
            print(f"✅ {ex.id} ({report.solution.duration_ms}ms)")
        else:
            failures += 1
            for problem in report.problems:
                print(f"❌ {ex.id}: {problem}")

    total = len(exercises) + len(loaded.errors)
    print(f"\n{total - failures}/{total} OK")
    return 1 if failures else 0


def try_code(exercise: Exercise, path: Path) -> int:
    """任意のコードで採点し、合否とケースごとの結果を表示する。合格なら 0。"""
    result = grade(exercise, path.read_text(encoding="utf-8"))
    for case in result.cases:
        print(f"{'✅' if case.passed else '❌'} {case.name}")
    verdict = "合格" if result.passed else f"不合格({result.error_type or '不明'})"
    print(f"\n{exercise.id}: {verdict} {result.passed_count}/{len(result.cases)}")
    return 0 if result.passed else 1


if __name__ == "__main__":
    sys.exit(main())
