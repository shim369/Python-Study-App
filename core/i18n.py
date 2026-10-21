"""画面に表示する文言の多言語対応(日本語 / 英語)。

文言は locales/<言語>.yaml にまとめ、コードでは "dashboard.title" のようなキーで参照する。
値の埋め込みは str.format の {name} 形式。

    t = Translator("en")
    t("exercise.attempts", count=2)  # -> "Attempts: 2"

英語の訳が無いキーは日本語にフォールバックする(翻訳漏れで画面が落ちないように)。
日本語にも無いキーはプログラムの誤りなので KeyError にする。
"""

import logging
from functools import cache
from pathlib import Path
from typing import Any, Literal, cast, get_args

import yaml

logger = logging.getLogger(__name__)

Lang = Literal["ja", "en"]
LANGUAGES: tuple[Lang, ...] = get_args(Lang)
DEFAULT_LANG: Lang = "ja"
# 言語の切り替えボタンの表示。どちらの言語を選んでいても読めるよう、両言語で書く
LANGUAGE_LABEL = "言語 / Language"
LANGUAGE_NAMES: dict[Lang, str] = {"ja": "日本語", "en": "English"}
# 選んだ言語を入れておく st.session_state のキー(切り替えボタンの widget の key でもある)
LANG_KEY = "lang"

LOCALES_DIR = Path(__file__).resolve().parent.parent / "locales"


def _flatten(tree: dict[str, Any], prefix: str = "") -> dict[str, str]:
    """入れ子の YAML を {"dashboard.title": "..."} のような1階層の辞書にする。"""
    flat: dict[str, str] = {}
    for key, value in tree.items():
        full_key = f"{prefix}{key}"
        if isinstance(value, dict):
            flat.update(_flatten(value, f"{full_key}."))
        else:
            flat[full_key] = str(value)
    return flat


@cache
def load_messages(lang: Lang) -> dict[str, str]:
    """その言語の文言を全部読み込む。ファイルは変わらないので1回だけ読む。"""
    path = LOCALES_DIR / f"{lang}.yaml"
    tree = yaml.safe_load(path.read_text(encoding="utf-8"))
    return _flatten(cast(dict[str, Any], tree))


def translate(lang: Lang, key: str, **values: object) -> str:
    messages = load_messages(lang)
    if key not in messages and lang != DEFAULT_LANG:
        logger.warning("翻訳がありません(%s): %s", lang, key)
        messages = load_messages(DEFAULT_LANG)
    return messages[key].format(**values)


def as_lang(value: object) -> Lang:
    """session_state などから取り出した値を Lang にする。知らない値なら既定の言語。"""
    return value if value in LANGUAGES else DEFAULT_LANG


class Translator:
    """言語を固定した translate。画面のコードでは t = Translator(lang) として t("key") と書く。"""

    def __init__(self, lang: Lang) -> None:
        self.lang = lang

    def __call__(self, key: str, **values: object) -> str:
        return translate(self.lang, key, **values)
