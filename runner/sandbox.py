"""学習者コードを別プロセスで実行するための最小限のサンドボックス。

できること:
- タイムアウト(超過時はプロセスグループごと強制終了)
- CPU時間・書き込みファイルサイズの制限(rlimit)
- 標準出力/標準エラーのサイズ上限
- 環境変数の除去(APIキーなどを子プロセスに渡さない)

できないこと(README参照): ネットワーク遮断、ファイルシステムの隔離、メモリ制限(macOS)。
ローカルで自分のコードを動かす用途に限定した仕組みであり、本格的なサンドボックスではない。
"""

import contextlib
import os
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

_LAUNCHER = Path(__file__).with_name("_launcher.py")


@dataclass(frozen=True)
class RunLimits:
    timeout_sec: float = 5.0
    max_output_bytes: int = 64_000
    max_file_bytes: int = 2_000_000


@dataclass(frozen=True)
class RunResult:
    returncode: int | None  # タイムアウト時は None
    stdout: str
    stderr: str
    duration_ms: int
    timed_out: bool
    truncated: bool

    @property
    def ok(self) -> bool:
        return self.returncode == 0 and not self.timed_out


def _safe_env(workdir: Path) -> dict[str, str]:
    """子プロセスに渡す環境変数。親の環境はコピーしない(ホワイトリスト方式)。"""
    return {
        "PATH": "/usr/bin:/bin",
        "HOME": str(workdir),
        "LANG": "C.UTF-8",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONHASHSEED": "0",
    }


def _read_capped(path: Path, limit: int) -> tuple[str, bool]:
    with path.open("rb") as f:
        data = f.read(limit + 1)
    truncated = len(data) > limit
    return data[:limit].decode("utf-8", errors="replace"), truncated


def _kill_group(proc: subprocess.Popen[bytes]) -> None:
    with contextlib.suppress(ProcessLookupError):  # 既に終了していれば何もしない
        os.killpg(proc.pid, signal.SIGKILL)
    proc.wait()


def run_python(
    args: list[str],
    workdir: Path,
    stdin: str = "",
    limits: RunLimits | None = None,
) -> RunResult:
    """`python -I <args>` を workdir で実行する。

    args 例: ["solution.py"] / ["-m", "pytest", "test_solution.py"]
    """
    limits = limits or RunLimits()
    cpu_sec = int(limits.timeout_sec) + 1
    command = [
        sys.executable,
        "-I",
        str(_LAUNCHER),
        str(cpu_sec),
        str(limits.max_file_bytes),
        "--",
        "-I",
        *args,
    ]

    # 出力ファイルは学習者の作業ディレクトリとは別の場所に置く
    with tempfile.TemporaryDirectory(prefix="study-out-") as out_dir:
        out_path = Path(out_dir) / "stdout"
        err_path = Path(out_dir) / "stderr"
        with out_path.open("wb") as out, err_path.open("wb") as err:
            started = time.perf_counter()
            proc = subprocess.Popen(
                command,
                cwd=workdir,
                env=_safe_env(workdir),
                stdin=subprocess.PIPE,
                stdout=out,
                stderr=err,
                start_new_session=True,  # 孫プロセスもまとめて kill できるようにする
            )
            timed_out = False
            try:
                proc.communicate(input=stdin.encode("utf-8"), timeout=limits.timeout_sec)
            except subprocess.TimeoutExpired:
                timed_out = True
                _kill_group(proc)
            duration_ms = int((time.perf_counter() - started) * 1000)

        stdout, out_truncated = _read_capped(out_path, limits.max_output_bytes)
        stderr, err_truncated = _read_capped(err_path, limits.max_output_bytes)

    return RunResult(
        returncode=None if timed_out else proc.returncode,
        stdout=stdout,
        stderr=stderr,
        duration_ms=duration_ms,
        timed_out=timed_out,
        truncated=out_truncated or err_truncated,
    )
