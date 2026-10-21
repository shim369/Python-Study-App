"""Streamlit のエントリポイント。設定の読み込み・ログ設定・言語の切り替え・ページ構成だけを行う。

起動: uv run streamlit run app/main.py
"""

import logging

import streamlit as st
from dotenv import load_dotenv

from core.i18n import (
    DEFAULT_LANG,
    LANG_KEY,
    LANGUAGE_LABEL,
    LANGUAGE_NAMES,
    LANGUAGES,
    Translator,
    as_lang,
)

load_dotenv()  # .env の設定(DBの保存先・APIキーなど)を環境変数として読み込む

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

st.set_page_config(page_title="Python-Study-App", page_icon="🐍", layout="wide")

# 表示言語の切り替え。各ページは st.session_state[LANG_KEY] を読んで文言を切り替える。
# この widget は全ページで毎回描画されるので、ページを移動しても選んだ言語が保たれる
st.sidebar.segmented_control(
    LANGUAGE_LABEL,
    options=LANGUAGES,
    format_func=LANGUAGE_NAMES.__getitem__,
    default=DEFAULT_LANG,
    required=True,  # 選択中のボタンをもう一度押しても「未選択」にならないようにする
    key=LANG_KEY,
)
t = Translator(as_lang(st.session_state.get(LANG_KEY)))

page = st.navigation(
    [
        st.Page("pages/exercise.py", title=t("nav.exercise"), default=True),
        st.Page("pages/dashboard.py", title=t("nav.dashboard")),
        st.Page("pages/playground.py", title=t("nav.playground")),
    ]
)
st.title("Python Study App")  # 全ページ共通の見出し(h1)。各ページの見出しは h2 にする
st.space(30)  # h1 の下に余白(px)を空ける
page.run()
