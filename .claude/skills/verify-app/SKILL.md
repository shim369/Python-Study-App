---
name: verify-app
description: Python-Study-App のコードや教材を変更した後、完了報告の前に必ず使う一括検証。pytest・ruff・mypy・全演習の模範解答検証を順に実行し、結果を要約して報告する。「検証して」「完了確認」「CIを回して」と言われた時や、実装作業の締めくくりに使う。
---

# verify-app

変更後の品質ゲート。**途中で失敗しても最後まで全ステップを実行**し、まとめて報告する。

## 手順
プロジェクトルートで以下を順に実行する。

1. `uv run pytest --cov=core --cov=runner --cov-report=term-missing`
2. `uv run ruff check .`
3. `uv run ruff format --check .`
4. `uv run mypy .`
5. `uv run python scripts/verify_solutions.py`(スクリプトが未作成のフェーズではスキップと明記)

## 報告フォーマット
```
| ステップ | 結果 | 補足 |
|---|---|---|
| pytest | ✅ 42 passed / カバレッジ core 91% runner 88% | |
| ruff check | ✅ | |
| ruff format | ❌ 2 files | app/main.py, core/srs.py |
| mypy | ✅ | |
| 模範解答検証 | ✅ 20/20 | |
```
- 失敗したステップはエラー出力の要点(ファイル:行とメッセージ)を引用する
- カバレッジが core / runner で 80% を下回ったら警告する
- 失敗を「軽微」と判断して省略しない。修正はユーザーの指示があるまで行わない(報告に専念)
