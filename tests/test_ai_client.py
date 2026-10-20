import re
from types import SimpleNamespace
from typing import Any

import pytest
from google.genai import errors

from ai.client import (
    DEFAULT_MODEL,
    AIError,
    GeminiClient,
    GeminiSettings,
    create_client,
    describe_api_error,
    settings_from_env,
)


def api_error(code: int, message: str = "error", status: str = "STATUS") -> errors.APIError:
    return errors.APIError(code, {"error": {"code": code, "message": message, "status": status}})


def test_no_api_key_disables_ai(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "  ")
    assert settings_from_env() is None
    assert create_client() is None


def test_settings_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "key")
    monkeypatch.delenv("GEMINI_MODEL", raising=False)
    assert settings_from_env() == GeminiSettings(api_key="key", model=DEFAULT_MODEL)

    monkeypatch.setenv("GEMINI_MODEL", "gemini-x")
    assert settings_from_env() == GeminiSettings(api_key="key", model="gemini-x")


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (api_error(429), "無料枠の利用上限"),
        (api_error(403), "APIキーが無効"),
        (api_error(400, "API key not valid. Please pass a valid API key."), "APIキーが無効"),
        (api_error(404), "モデルが見つかりません"),
        (api_error(503), "一時的なエラー"),
        (api_error(400, "bad request", "INVALID_ARGUMENT"), "400 INVALID_ARGUMENT"),
    ],
)
def test_describe_api_error(error: errors.APIError, expected: str) -> None:
    assert expected in describe_api_error(error)


class FakeResponse:
    def __init__(self, text: str | None) -> None:
        self.text = text


class FakeModels:
    """genai.Client().models の代わり。決まった応答を返すか、例外を投げる。"""

    def __init__(self, outcome: str | Exception | None) -> None:
        self.outcome = outcome
        self.kwargs: dict[str, Any] = {}

    def generate_content(self, **kwargs: Any) -> FakeResponse:
        self.kwargs = kwargs
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return FakeResponse(self.outcome)


def client_with(outcome: str | Exception | None) -> tuple[GeminiClient, FakeModels]:
    client = GeminiClient(GeminiSettings(api_key="dummy", model="gemini-test"))
    models = FakeModels(outcome)
    # 通信せずに済むよう、SDK のクライアントごと「.models を持つだけの偽物」に差し替える
    client._client = SimpleNamespace(models=models)  # type: ignore[assignment]
    return client, models


def test_generate_returns_text_and_sends_system_prompt() -> None:
    client, models = client_with("こたえ")
    assert client.generate("system", "prompt") == "こたえ"
    assert models.kwargs["model"] == "gemini-test"
    assert models.kwargs["contents"] == "prompt"
    assert models.kwargs["config"].system_instruction == "system"


@pytest.mark.parametrize(
    ("outcome", "expected"),
    [
        (api_error(429), "無料枠の利用上限"),
        (ConnectionError("down"), "接続できませんでした(ConnectionError)"),
        (None, "回答が得られませんでした"),
    ],
)
def test_generate_failures_become_ai_error(outcome: Exception | None, expected: str) -> None:
    client, _ = client_with(outcome)
    with pytest.raises(AIError, match=re.escape(expected)):
        client.generate("system", "prompt")
