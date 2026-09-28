"""Local launcher process and binding checks without a GPU or model download."""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import time
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def _fake_launcher(tmp_path: Path) -> tuple[Path, dict[str, str]]:
    root = tmp_path / "demo"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    for name in ("start_vllm.sh", "start_all.sh"):
        shutil.copy2(SCRIPTS / name, scripts / name)

    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    fake_python = fake_bin / "python"
    fake_python.write_text(
        "#!/usr/bin/env python3\n"
        "import os, sys, time\n"
        "with open(os.environ['FAKE_CALLS_FILE'], 'a', encoding='utf-8') as f:\n"
        "    f.write(' '.join(sys.argv[1:]) + '\\n')\n"
        "if sys.argv[1:] == ['-m', 'json.tool']:\n"
        "    print(sys.stdin.read())\n"
        "else:\n"
        "    time.sleep(60)\n",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)
    fake_curl = fake_bin / "curl"
    fake_curl.write_text(
        "#!/bin/sh\ncase \"$*\" in\n  *'/v1/models'*) printf '{\"data\":[]}\\n' ;;\nesac\nexit 0\n",
        encoding="utf-8",
    )
    fake_curl.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{fake_bin}:{os.environ['PATH']}",
        "FAKE_CALLS_FILE": str(tmp_path / "calls.txt"),
    }
    return root, env


def _stop(pid: int) -> None:
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass


def test_model_launcher_binds_loopback_and_records_model_pid(tmp_path: Path) -> None:
    root, env = _fake_launcher(tmp_path)
    try:
        result = subprocess.run(
            ["bash", "scripts/start_vllm.sh", "0"],
            cwd=root,
            env=env,
            text=True,
            capture_output=True,
            timeout=10,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        pid = int((root / "logs/vllm.pid").read_text(encoding="utf-8"))
        os.kill(pid, 0)
        calls = (tmp_path / "calls.txt").read_text(encoding="utf-8")
        assert "vllm.entrypoints.openai.api_server" in calls
        assert "--host 127.0.0.1" in calls
        assert "--host 0.0.0.0" not in calls
    finally:
        if (root / "logs/vllm.pid").exists():
            _stop(int((root / "logs/vllm.pid").read_text(encoding="utf-8")))


def test_combined_launcher_stops_both_services_on_shutdown(tmp_path: Path) -> None:
    root, env = _fake_launcher(tmp_path)
    process = subprocess.Popen(
        ["bash", "scripts/start_all.sh", "0"],
        cwd=root,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    model_pid = None
    api_pid = None
    try:
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            model_file = root / "logs/vllm.pid"
            api_file = root / "logs/api.pid"
            if model_file.exists() and api_file.exists():
                model_pid = int(model_file.read_text(encoding="utf-8"))
                api_pid = int(api_file.read_text(encoding="utf-8"))
                break
            time.sleep(0.05)
        assert model_pid is not None and api_pid is not None
        os.kill(model_pid, 0)
        os.kill(api_pid, 0)
        # The API PID file is written before the background Python process
        # records its arguments. Wait for that independent process to start.
        calls = ""
        call_deadline = time.monotonic() + 5
        while time.monotonic() < call_deadline:
            calls = (tmp_path / "calls.txt").read_text(encoding="utf-8")
            if calls.count("--host 127.0.0.1") == 2:
                break
            time.sleep(0.05)
        assert calls.count("--host 127.0.0.1") == 2

        process.send_signal(signal.SIGTERM)
        process.communicate(timeout=10)
        assert process.returncode == 143
        assert not (root / "logs/vllm.pid").exists()
        assert not (root / "logs/api.pid").exists()
    finally:
        if process.poll() is None:
            process.kill()
            process.communicate(timeout=10)
        if model_pid is not None:
            _stop(model_pid)
        if api_pid is not None:
            _stop(api_pid)
