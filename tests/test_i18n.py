import re

import pytest

from core.i18n import DEFAULT_LANG, LANGUAGES, Translator, as_lang, load_messages, translate

PLACEHOLDER = re.compile(r"\{(\w+)\}")


@pytest.mark.parametrize("lang", [lang for lang in LANGUAGES if lang != DEFAULT_LANG])
def test_all_languages_have_the_same_keys(lang: str) -> None:
    """翻訳漏れ(片方にしか無いキー)を見つける。"""
    base = load_messages(DEFAULT_LANG)
    other = load_messages(as_lang(lang))
    assert set(other) == set(base)


@pytest.mark.parametrize("lang", [lang for lang in LANGUAGES if lang != DEFAULT_LANG])
def test_placeholders_match(lang: str) -> None:
    """{count} などの埋め込み先が言語によって違うと、format で KeyError になる。"""
    base = load_messages(DEFAULT_LANG)
    other = load_messages(as_lang(lang))
    for key, text in base.items():
        assert set(PLACEHOLDER.findall(other[key])) == set(PLACEHOLDER.findall(text)), key


def test_translate_fills_values() -> None:
    assert translate("ja", "exercise.attempts", count=2) == "挑戦回数: 2"
    assert Translator("en")("exercise.attempts", count=2) == "Attempts: 2"


def test_missing_key_falls_back_to_japanese(monkeypatch: pytest.MonkeyPatch) -> None:
    english = {k: v for k, v in load_messages("en").items() if k != "nav.dashboard"}
    monkeypatch.setattr(
        "core.i18n.load_messages", lambda lang: english if lang == "en" else load_messages(lang)
    )
    assert translate("en", "nav.dashboard") == "ダッシュボード"


def test_unknown_key_is_an_error() -> None:
    with pytest.raises(KeyError):
        translate("en", "no.such.key")


def test_as_lang() -> None:
    assert as_lang("en") == "en"
    assert as_lang(None) == DEFAULT_LANG
    assert as_lang("fr") == DEFAULT_LANG
