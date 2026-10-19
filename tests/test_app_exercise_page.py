"""演習ページのスモークテスト(Streamlit の AppTest でブラウザなしに画面を動かす)。"""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from core.loader import load_all

MAIN_SCRIPT = Path(__file__).resolve().parent.parent / "app" / "main.py"
FIRST = load_all().exercises[0]
EDITOR_KEY = f"editor:{FIRST.id}:0"


@pytest.fixture
def app() -> AppTest:
    return AppTest.from_file(str(MAIN_SCRIPT), default_timeout=30).run()


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
