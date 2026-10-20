"""Streamlit のエントリポイント。設定の読み込み・ログ設定・ページ構成だけを行う。

起動: uv run streamlit run app/main.py
"""

import logging

import streamlit as st
from dotenv import load_dotenv

load_dotenv()  # .env の設定(DBの保存先・APIキーなど)を環境変数として読み込む

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

st.set_page_config(page_title="Python-Study-App", page_icon="🐍", layout="wide")

page = st.navigation(
    [
        st.Page("pages/exercise.py", title="演習", icon="✍️", default=True),
        st.Page("pages/dashboard.py", title="ダッシュボード", icon="📊"),
        st.Page("pages/playground.py", title="自由に試す", icon="🧪"),
    ]
)
page.run()
