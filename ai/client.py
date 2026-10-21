"""Gemini API の薄いラッパー。

- 設定は環境変数(.env)から読む。APIキーが無ければ create_client() は None を返し、
  呼び出し側は「AI機能なし」で動き続ける
- API のエラーは AIError(学習者に見せてよいメッセージ付き)に変換する。
  メッセージは locales/ の ai_error.* にあり、画面の言語で表示できる
"""

import logging
import os
from dataclasses import dataclass
from typing import Protocol

from google import genai
from google.genai import errors, types

from core.i18n import DEFAULT_LANG, Lang, translate

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-3.8-flash"
TIMEOUT_MS = 60_000


class AIError(Exception):
    """AI の呼び出しに失敗した。message(lang) で画面に表示できるメッセージになる。

    key は locales/ の文言のキー(例: "ai_error.rate_limit")。str(e) は日本語(ログ用)。
    """

    def __init__(self, key: str, **values: object) -> None:
        self.key = key
        self.values = values
        super().__init__(self.message(DEFAULT_LANG))

    def message(self, lang: Lang) -> str:
        return translate(lang, self.key, **self.values)


class TextGenerator(Protocol):
    """文章生成の窓口。テストでは偽物に差し替えられるよう、型だけを決めておく。"""

    def generate(self, system: str, prompt: str) -> str: ...


@dataclass(frozen=True)
class GeminiSettings:
    api_key: str
    model: str = DEFAULT_MODEL


def settings_from_env() -> GeminiSettings | None:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        return None
    model = os.environ.get("GEMINI_MODEL", "").strip() or DEFAULT_MODEL
    return GeminiSettings(api_key=api_key, model=model)


class GeminiClient:
    def __init__(self, settings: GeminiSettings) -> None:
        self.model = settings.model
        self._client = genai.Client(
            api_key=settings.api_key,
            http_options=types.HttpOptions(timeout=TIMEOUT_MS),
        )

    def generate(self, system: str, prompt: str) -> str:
        try:
            response = self._client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(system_instruction=system),
            )
        except errors.APIError as e:
            logger.exception("Gemini API がエラーを返しました")
            raise to_ai_error(e) from e
        except Exception as e:  # 通信エラーなど。AI機能だけを失敗扱いにしてアプリは続ける
            logger.exception("Gemini API の呼び出しに失敗しました")
            raise AIError("ai_error.connection", name=type(e).__name__) from e

        if not response.text:
            logger.error("Gemini API の応答が空でした: %s", response)
            raise AIError("ai_error.empty")
        return response.text


def to_ai_error(error: errors.APIError) -> AIError:
    """HTTPステータスから、学習者が次に何をすればよいか分かるメッセージの AIError を作る。"""
    if error.code == 429:
        return AIError("ai_error.rate_limit")
    if error.code in (401, 403) or (error.code == 400 and "API key" in (error.message or "")):
        return AIError("ai_error.invalid_key")
    if error.code == 404:
        return AIError("ai_error.model_not_found")
    if error.code >= 500:
        return AIError("ai_error.server_error")
    return AIError("ai_error.other", code=error.code, status=error.status)


def create_client() -> GeminiClient | None:
    settings = settings_from_env()
    if settings is None:
        logger.info("GEMINI_API_KEY が未設定のため、AI機能は無効です")
        return None
    return GeminiClient(settings)
