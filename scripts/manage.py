#!/usr/bin/env python3
"""Local project launcher. Uses only the Python standard library."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
PYTHON = BACKEND / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")


def run(command: list[str], cwd: Path = ROOT) -> None:
    print("+ " + " ".join(command), flush=True)
    subprocess.run(command, cwd=cwd, check=True)


def npm() -> str:
    executable = shutil.which("npm.cmd" if os.name == "nt" else "npm")
    if not executable:
        raise RuntimeError("请安装 Node.js 22.12+（包含 npm），然后重新运行。")
    return executable


def require_backend() -> None:
    if not PYTHON.is_file():
        raise RuntimeError("尚未安装后端依赖，请先运行 ./scripts/setup.sh")


def setup() -> None:
    if sys.version_info < (3, 11):
        raise RuntimeError("需要 Python 3.11 或更新版本。")
    if not PYTHON.is_file():
        run([sys.executable, "-m", "venv", str(BACKEND / ".venv")])
    run([str(PYTHON), "-m", "pip", "install", "-c", "requirements.lock.txt", "-e", ".[dev]"], BACKEND)
    run([npm(), "ci" if (FRONTEND / "package-lock.json").is_file() else "install"], FRONTEND)


def supervise(commands: list[tuple[list[str], Path]]) -> None:
    children: list[subprocess.Popen] = []
    exit_code = 0

    def request_stop(signum: int, _frame: object) -> None:
        raise KeyboardInterrupt

    previous = {s: signal.signal(s, request_stop) for s in (signal.SIGINT, signal.SIGTERM)}
    try:
        for command, directory in commands:
            print("+ " + " ".join(command), flush=True)
            children.append(subprocess.Popen(command, cwd=directory, start_new_session=os.name != "nt"))
        while True:
            for child in children:
                code = child.poll()
                if code is not None:
                    exit_code = code
                    if code:
                        print(f"服务退出（代码 {code}），正在关闭其他进程。", file=sys.stderr)
                    return
            time.sleep(0.3)
    except KeyboardInterrupt:
        print("\n正在关闭工具箱服务…", flush=True)
    finally:
        # Signal the whole process group so npm/Vite and uvicorn reload children
        # cannot remain listening after the launcher exits.
        for child in reversed(children):
            try:
                if os.name == "nt":
                    child.terminate()
                else:
                    os.killpg(child.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        deadline = time.monotonic() + 12
        for child in children:
            try:
                child.wait(timeout=max(0.1, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                try:
                    if os.name == "nt":
                        child.kill()
                    else:
                        os.killpg(child.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                child.wait()
        for s, handler in previous.items():
            signal.signal(s, handler)
        if exit_code:
            raise SystemExit(exit_code)


def serve(development: bool) -> None:
    require_backend()
    api_port = str(int(os.environ.get("LEE_TOOLBOX_API_PORT", "8000")))
    web_port = str(int(os.environ.get("LEE_TOOLBOX_WEB_PORT", "5173")))
    api_command = [str(PYTHON), "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", api_port]
    commands = []
    if development:
        if not (FRONTEND / "node_modules").is_dir():
            raise RuntimeError("尚未安装前端依赖，请先运行 ./scripts/setup.sh")
        api_command += ["--reload", "--reload-dir", str(BACKEND / "app")]
        commands.append((api_command, BACKEND))
        commands.append(([npm(), "run", "dev", "--", "--host", "127.0.0.1", "--port", web_port, "--strictPort"], FRONTEND))
        print(f"工具箱开发地址：http://127.0.0.1:{web_port}", flush=True)
    else:
        if not (FRONTEND / "dist/index.html").is_file():
            raise RuntimeError("尚未构建界面，请先运行 ./scripts/build.sh")
        commands.append((api_command, BACKEND))
        print(f"工具箱地址：http://127.0.0.1:{api_port}", flush=True)
    supervise(commands)


def main() -> None:
    parser = argparse.ArgumentParser(description="Lee Toolbox 本地开发与启动")
    parser.add_argument("action", choices=("setup", "dev", "build", "start", "test"))
    action = parser.parse_args().action
    try:
        if action == "setup":
            setup()
        elif action == "build":
            run([npm(), "run", "build"], FRONTEND)
        elif action == "test":
            require_backend()
            run([str(PYTHON), "-m", "pytest", "-q"], BACKEND)
            run([npm(), "test", "--", "--run"], FRONTEND)
            run([npm(), "run", "build"], FRONTEND)
        else:
            serve(action == "dev")
    except (RuntimeError, ValueError) as exc:
        print(f"错误：{exc}", file=sys.stderr)
        raise SystemExit(1)
    except subprocess.CalledProcessError as exc:
        raise SystemExit(exc.returncode)


if __name__ == "__main__":
    main()
