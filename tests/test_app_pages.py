"""画面のスモークテスト(Streamlit の AppTest でブラウザなしに画面を動かす)。"""

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

import ai.feedback
from core.loader import load_all
from core.models import GradeResult
from core.progress import ProgressStore

MAIN_SCRIPT = Path(__file__).resolve().parent.parent / "app" / "main.py"
FIRST = load_all().exercises[0]
EDITOR_KEY = f"editor:{FIRST.id}:0"


@pytest.fixture(autouse=True)
def isolated_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """本物の data/app.db を汚さないよう、テストごとに一時DBを使う。"""
    path = tmp_path / "app.db"
    monkeypatch.setenv("STUDY_APP_DB_PATH", str(path))
    return path


@pytest.fixture(autouse=True)
def no_real_ai(monkeypatch: pytest.MonkeyPatch) -> None:
    """.env に本物のキーがあっても、テストでは Gemini を呼ばない(AI無効の状態から始める)。"""
    monkeypatch.setenv("GEMINI_API_KEY", "")  # load_dotenv は設定済みの環境変数を上書きしない
    st.cache_resource.clear()  # AI サービスはプロセス内でキャッシュされるので毎回作り直す


class FakeGenerator:
    def generate(self, system: str, prompt: str) -> str:
        return "AIの回答です"


def start_app() -> AppTest:
    return AppTest.from_file(str(MAIN_SCRIPT), default_timeout=30).run()


@pytest.fixture
def app() -> AppTest:
    return start_app()


def shown_code(app: AppTest) -> list[str]:
    # st.code は末尾の改行を落として表示するので、比較用に揃える
    return [block.value.rstrip() for block in app.code]


def click(app: AppTest, label: str) -> None:
    next(b for b in app.button if b.label == label).click().run()


def test_page_shows_first_exercise(app: AppTest) -> None:
    assert not app.exception
    assert app.title[0].value == FIRST.title


def test_starter_code_fails(app: AppTest) -> None:
    click(app, "▶ 実行")
    assert app.error[0].value.startswith("不合格")
    assert FIRST.solution.rstrip() not in shown_code(app)  # 模範解答はまだ見えない


def test_solution_passes_and_reveals_solution(app: AppTest) -> None:
    app.session_state[EDITOR_KEY] = FIRST.solution  # エディタに模範解答を入力した状態
    click(app, "▶ 実行")
    assert app.success[0].value.startswith("合格")  # 先頭の絵文字は icon として分離される
    assert FIRST.solution.rstrip() in shown_code(app)


def test_hints_are_shown_step_by_step(app: AppTest) -> None:
    click(app, "ヒント1を見る(全3段階)")
    assert len(app.info) == 1
    click(app, "ヒント2を見る(全3段階)")
    assert len(app.info) == 2


def test_progress_survives_restart(app: AppTest) -> None:
    click(app, "ヒント1を見る(全3段階)")
    app.session_state[EDITOR_KEY] = FIRST.solution
    click(app, "▶ 実行")

    restarted = start_app()  # 新しいセッション = アプリ再起動に相当
    assert not restarted.exception
    assert len(restarted.info) == 1  # 開いたヒントが復元される
    assert FIRST.solution.rstrip() in shown_code(restarted)  # 合格済みなので模範解答が見える
    assert restarted.sidebar.selectbox[0].options[0].startswith("✅")  # 一覧にも合格マーク


def test_dashboard_shows_progress(app: AppTest) -> None:
    app.session_state[EDITOR_KEY] = FIRST.solution
    click(app, "▶ 実行")

    app.switch_page("pages/dashboard.py").run()
    assert not app.exception
    assert app.title[0].value == "ダッシュボード"
    assert app.metric[0].value.startswith("1 /")  # 合格した問題
    assert app.metric[1].value == "1 日"  # 連続学習日数


def test_ai_disabled_without_api_key(app: AppTest) -> None:
    assert not app.exception
    assert any("GEMINI_API_KEY" in c.value for c in app.caption)
    assert not any(b.label.startswith("AIヒント") for b in app.button)


def test_ai_buttons_follow_practice_state(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(ai.feedback, "create_client", FakeGenerator)
    app = start_app()

    def button(prefix: str) -> Any:
        return next(b for b in app.button if b.label.startswith(prefix))

    assert button("不合格の原因").disabled  # まだ実行していない
    assert button("コードレビュー").disabled

    click(app, "AIヒント(1/3)")
    assert any(e.label == "AIヒント(段階1)" for e in app.expander)
    assert any(m.value == "AIの回答です" for m in app.markdown)
    assert button("AIヒント(2/3)")  # 次の段階に進んでいる

    click(app, "▶ 実行")  # 初期コードは不合格
    assert not button("不合格の原因").disabled
    button("不合格の原因").click().run()
    assert any(e.label == "不合格の原因" for e in app.expander)

    app.session_state[EDITOR_KEY] = FIRST.solution
    click(app, "▶ 実行")
    assert not button("コードレビュー").disabled


def test_selection_is_kept_when_label_changes(app: AppTest) -> None:
    """実行して ✏️ / ✅ が付いても、選んだ問題のまま操作を続けられる。"""
    second = load_all().exercises[1]
    app.sidebar.selectbox[0].select_index(1).run()
    assert app.title[0].value == second.title

    click(app, "▶ 実行")  # 初期コードで不合格 → ラベルに ✏️ が付く
    assert app.sidebar.selectbox[0].options[1].startswith("✏️")
    click(app, "▶ 実行")
    assert not app.exception
    assert app.title[0].value == second.title
    assert any(c.value == "挑戦回数: 2" for c in app.caption)


def test_selection_survives_page_switch(app: AppTest) -> None:
    second = load_all().exercises[1]
    app.sidebar.selectbox[0].select_index(1).run()
    app.switch_page("pages/dashboard.py").run()
    app.switch_page("pages/exercise.py").run()
    assert app.title[0].value == second.title


def test_dashboard_todo_opens_exercise(app: AppTest) -> None:
    app.switch_page("pages/dashboard.py").run()
    todo_buttons = [b for b in app.button if b.label == "解く"]
    todo_buttons[1].click().run()  # 何もしていなければカリキュラム順。2番目の問題を開く
    assert not app.exception
    assert app.title[0].value == load_all().exercises[1].title


def test_due_review_is_marked(isolated_db: Path) -> None:
    two_days_ago = datetime.now().astimezone() - timedelta(days=2)
    ProgressStore(isolated_db).record_attempt(FIRST.id, GradeResult(passed=True), two_days_ago)

    app = start_app()
    assert app.sidebar.selectbox[0].options[0].startswith("🔁")
    assert any("復習の時期です(1回目)" in i.value for i in app.info)

    app.switch_page("pages/dashboard.py").run()
    assert any(m.value == "🔁 復習(1回目)" for m in app.markdown)


def test_playground_runs_code(app: AppTest) -> None:
    app.switch_page("pages/playground.py").run()
    assert app.title[0].value == "自由に試す"
    click(app, "▶ 実行")
    assert not app.exception
    assert app.success[0].value.startswith("実行しました")
    assert "python: 3" in app.code[0].value  # サンプルコードの出力
    assert any("GEMINI_API_KEY" in c.value for c in app.caption)  # AI は無効


def test_playground_ai_review(monkeypatch: pytest.MonkeyPatch, app: AppTest) -> None:
    monkeypatch.setattr(ai.feedback, "create_client", FakeGenerator)
    app.switch_page("pages/playground.py").run()
    click(app, "このコードをレビューしてもらう")
    assert any(m.value == "AIの回答です" for m in app.markdown)


def test_dashboard_has_export_buttons(app: AppTest) -> None:
    app.switch_page("pages/dashboard.py").run()
    # download_button 専用の取得メソッドが無いので、要素の種類で探して proto からラベルを読む
    labels = [e.proto.label for e in app.get("download_button")]
    assert labels == ["挑戦履歴(CSV)", "進捗と履歴(JSON)"]
