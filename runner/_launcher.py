"""子プロセス側で資源制限をかけてから本体を exec するランチャー。

使い方: python -I _launcher.py <cpu_sec> <file_size_bytes> -- <python引数...>

親プロセスで preexec_fn を使うとスレッド環境(Streamlit)で危険なため、
制限の設定はこの別プロセス内で行い、os.execv で Python 本体に置き換える。
rlimit は exec 後も引き継がれる。
"""

import contextlib
import os
import resource
import sys


def _set_limit(kind: int, value: int) -> None:
    _soft, hard = resource.getrlimit(kind)
    if hard != resource.RLIM_INFINITY:
        value = min(value, hard)
    # OSによっては設定できない制限がある(例: macOS の一部)。その場合も実行自体は続ける
    with contextlib.suppress(ValueError, OSError):
        resource.setrlimit(kind, (value, hard))


def main() -> None:
    cpu_sec = int(sys.argv[1])
    file_size = int(sys.argv[2])
    separator = sys.argv.index("--")
    python_args = sys.argv[separator + 1 :]

    _set_limit(resource.RLIMIT_CPU, cpu_sec)
    _set_limit(resource.RLIMIT_FSIZE, file_size)
    _set_limit(resource.RLIMIT_CORE, 0)

    os.execv(sys.executable, [sys.executable, *python_args])


if __name__ == "__main__":
    main()
