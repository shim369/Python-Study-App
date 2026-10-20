"""画面のスモークテスト(Streamlit の AppTest でブラウザなしに画面を動かす)。"""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from core.loader import load_all

MAIN_SCRIPT = Path(__file__).resolve().parent.parent / "app" / "main.py"
FIRST = load_all().exercises[0]
EDITOR_KEY = f"editor:{FIRST.id}:0"


@pytest.fixture(autouse=True)
def isolated_db(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """本物の data/app.db を汚さないよう、テストごとに一時DBを使う。"""
    path = tmp_path / "app.db"
    monkeypatch.setenv("STUDY_APP_DB_PATH", str(path))
    return path


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
