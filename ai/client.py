"""Gemini API の薄いラッパー。

- 設定は環境変数(.env)から読む。APIキーが無ければ create_client() は None を返し、
  呼び出し側は「AI機能なし」で動き続ける
- API のエラーは AIError(学習者に見せてよいメッセージ付き)に変換する
"""

import logging
import os
from dataclasses import dataclass
from typing import Protocol

from google import genai
from google.genai import errors, types

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "gemini-3.8-flash"
TIMEOUT_MS = 60_000


class AIError(Exception):
    """AI の呼び出しに失敗した。メッセージはそのまま画面に表示できる。"""


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
            raise AIError(describe_api_error(e)) from e
        except Exception as e:  # 通信エラーなど。AI機能だけを失敗扱いにしてアプリは続ける
            logger.exception("Gemini API の呼び出しに失敗しました")
            raise AIError(f"AI に接続できませんでした({type(e).__name__})") from e

        if not response.text:
            logger.error("Gemini API の応答が空でした: %s", response)
            raise AIError("AI から回答が得られませんでした。少し時間をおいて試してください。")
        return response.text


def describe_api_error(error: errors.APIError) -> str:
    """HTTPステータスから、学習者が次に何をすればよいか分かるメッセージを作る。"""
    if error.code == 429:
        return "無料枠の利用上限に達しました。しばらく待つか、GEMINI_MODEL を変えて試してください。"
    if error.code in (401, 403) or (error.code == 400 and "API key" in (error.message or "")):
        return "APIキーが無効です。.env の GEMINI_API_KEY を確認してください。"
    if error.code == 404:
        return "モデルが見つかりません。.env の GEMINI_MODEL を確認してください。"
    if error.code >= 500:
        return "AI サービス側で一時的なエラーが起きました。少し時間をおいて試してください。"
    return f"AI の呼び出しに失敗しました({error.code} {error.status})"


def create_client() -> GeminiClient | None:
    settings = settings_from_env()
    if settings is None:
        logger.info("GEMINI_API_KEY が未設定のため、AI機能は無効です")
        return None
    return GeminiClient(settings)
