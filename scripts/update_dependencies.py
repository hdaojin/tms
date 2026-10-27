"""在开发机更新依赖并验证；不提交、不推送、不操作服务器。"""

import argparse
import os
import shlex
import shutil
import subprocess
import sys
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parent.parent


def build_commands(target):
    commands = []
    if target in {"python", "all"}:
        commands.extend([["uv", "lock", "--upgrade"], ["uv", "sync", "--locked"]])
    if target in {"npm", "all"}:
        commands.extend(
            [
                ["npm", "update", "--package-lock-only", "--include=dev"],
                ["npm", "ci", "--include=dev"],
                ["npm", "run", "build:frontend"],
                ["npm", "run", "test:frontend"],
            ]
        )
    if target in {"python", "all"}:
        commands.extend(
            [
                ["uv", "lock", "--check"],
                ["uv", "run", "--locked", "ruff", "check", "."],
                ["uv", "run", "--locked", "manage.py", "check"],
                ["uv", "run", "--locked", "manage.py", "makemigrations", "--check", "--dry-run"],
                ["uv", "run", "--locked", "pytest"],
            ]
        )
    commands.extend([["git", "diff", "--check"], ["git", "diff", "--stat"], ["git", "status", "--short"]])
    return commands


def run_command(command, environment):
    executable = shutil.which(command[0])
    if executable is None:
        raise RuntimeError(f"缺少命令：{command[0]}")
    print(f"\n$ {shlex.join(command)}", flush=True)
    subprocess.run([executable, *command[1:]], cwd=REPOSITORY, env=environment, check=True)


def require_development_checkout():
    if (REPOSITORY / ".tms-release-sha").exists() or not (REPOSITORY / ".git").exists():
        raise RuntimeError("此脚本只能在开发 Git 工作区运行，不能在服务器 release 或源码归档中运行。")
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("缺少命令：git")
    status = subprocess.run(
        [git, "status", "--porcelain", "--untracked-files=normal"],
        cwd=REPOSITORY,
        check=True,
        capture_output=True,
        text=True,
    )
    if status.stdout.strip():
        raise RuntimeError("工作区存在未提交修改或未跟踪文件；请先独立保存这些修改，再更新依赖。")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("target", choices=("python", "npm", "all"), help="更新 Python、npm 或全部依赖")
    parser.add_argument("--dry-run", action="store_true", help="仅输出命令，不安装、不构建、不更新锁文件")
    args = parser.parse_args(argv)
    commands = build_commands(args.target)
    if args.dry_run:
        for command in commands:
            print(shlex.join(command))
        return 0

    try:
        require_development_checkout()
        for command in commands:
            if shutil.which(command[0]) is None:
                raise RuntimeError(f"缺少命令：{command[0]}")
        environment = os.environ.copy()
        environment["UV_CACHE_DIR"] = str(REPOSITORY / ".uv-cache")
        for command in commands:
            run_command(command, environment)
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"更新停止：{exc}\n已产生的变更保留供检查；脚本不会自动重置文件。", file=sys.stderr)
        return 1

    print("\n依赖更新与检查完成。请审阅锁文件和静态产物，再人工提交、推送并部署对应 SHA。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
