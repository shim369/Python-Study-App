# Python-Study-App

Pythonコードを書いて実行 → 自動採点 → AIフィードバックで学ぶ、ローカル専用の学習Webアプリ。
学習者はPHP実務経験者。**コードは読みやすさと学びやすさを最優先**にする。

## 技術スタック
- Python 3.12+ / Streamlit(`st.navigation`)/ uv / SQLite(標準 `sqlite3`)
- Gemini API 無料枠(`google-genai` SDK、モデルは `GEMINI_MODEL` で切替)
- pytest / ruff / mypy --strict / pydantic v2 / PyYAML

## ディレクトリ
- `app/` Streamlit UI層(薄く保つ。ロジックを書かない)
- `core/` ドメインロジック(採点・進捗・間隔反復・おすすめ)。**Streamlitをimportしない**
- `runner/` 学習者コードの隔離実行(subprocess + タイムアウト + 出力上限)
- `ai/` Gemini APIクライアントとフィードバック生成(キー未設定・失敗時もアプリは落ちない)
- `prompts/` AIプロンプト(**コード内にプロンプト文をハードコードしない**)
- `exercises/level{N}/<NNN_slug>/` 教材(`exercise.yaml` + `test_solution.py`)
- `scripts/verify_solutions.py` 全演習の模範解答検証

## よく使うコマンド
```
uv run streamlit run app/main.py      # アプリ起動
uv run pytest                         # テスト
uv run pytest --cov=core --cov=runner # カバレッジ
uv run ruff check . && uv run ruff format .
uv run mypy .
uv run python scripts/verify_solutions.py
```

## コーディング規約
- 全関数に型ヒント(mypy --strict が通ること)
- 依存追加は `uv add`(開発用は `uv add --dev`)。pip / requirements.txt は使わない
- **新規ライブラリを追加する前に、理由を説明して承認を得る**
- 例外は握りつぶさない。ユーザーに分かる形で表示し、`logging` にも残す
- テストを通すためにテストを弱めない。テストが誤りなら理由を説明してから直す

## 完了報告のルール
- 実装後は必ず `pytest`・`ruff check`・`mypy` を実行し、全て通ってから完了報告する
  (`verify-app` Skill でまとめて実行できる)
- 動かして確認していないコードを「完成」と報告しない

## Skills
- `add-exercise` 演習を1問追加 / `review-exercise` 演習の品質レビュー / `verify-app` 一括検証
