"""設定ファイルの読み込みと検証 のテスト。学習者のコードは solution.py として配置される。"""

import json

import pytest

from solution import Config, ConfigError, load_config


def test_minimal_config_uses_defaults() -> None:
    assert load_config('{"host": "localhost", "port": 8080}') == Config("localhost", 8080)


def test_full_config() -> None:
    text = json.dumps(
        {"host": "example.com", "port": 443, "debug": True, "allowed_hosts": ["a", "b"]}
    )
    assert load_config(text) == Config("example.com", 443, True, ("a", "b"))


@pytest.mark.parametrize("port", [1, 65535])
def test_port_boundaries(port: int) -> None:
    assert load_config(json.dumps({"host": "h", "port": port})).port == port


def test_invalid_json_chains_original_error() -> None:
    with pytest.raises(ConfigError) as info:
        load_config("{host: localhost}")
    assert isinstance(info.value.__cause__, json.JSONDecodeError)


@pytest.mark.parametrize("text", ["[]", '"text"', "123", "null"])
def test_top_level_must_be_object(text: str) -> None:
    with pytest.raises(ConfigError):
        load_config(text)


@pytest.mark.parametrize(
    ("data", "key"),
    [
        ({"port": 80}, "host"),  # 必須キーが無い
        ({"host": "h"}, "port"),
        ({"host": "", "port": 80}, "host"),  # 空文字列
        ({"host": 1, "port": 80}, "host"),
        ({"host": "h", "port": "80"}, "port"),  # 文字列の数字
        ({"host": "h", "port": 80.0}, "port"),  # 小数
        ({"host": "h", "port": True}, "port"),  # bool は int のサブクラス
        ({"host": "h", "port": 0}, "port"),  # 範囲外
        ({"host": "h", "port": 65536}, "port"),
        ({"host": "h", "port": 80, "debug": "yes"}, "debug"),
        ({"host": "h", "port": 80, "debug": 1}, "debug"),
        ({"host": "h", "port": 80, "allowed_hosts": "a"}, "allowed_hosts"),
        ({"host": "h", "port": 80, "allowed_hosts": ["a", 1]}, "allowed_hosts"),
        ({"host": "h", "port": 80, "timeout": 3}, "timeout"),  # 未知のキー
    ],
)
def test_invalid_values_mention_key(data: dict[str, object], key: str) -> None:
    with pytest.raises(ConfigError, match=key):
        load_config(json.dumps(data))
