"""Streamlit のエントリポイント。ページ構成とログ設定だけを行う。

起動: uv run streamlit run app/main.py
"""

import logging

import streamlit as st

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

st.set_page_config(page_title="Python-Study-App", page_icon="🐍", layout="wide")

page = st.navigation(
    [
        st.Page("pages/exercise.py", title="演習", icon="✍️", default=True),
    ]
)
page.run()
