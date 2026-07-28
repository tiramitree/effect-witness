"""Disposable synthetic Git fixture for the schema-v5 coding-agent lane."""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

from .artifact import _is_link_or_reparse
from .coding_registration import REGISTERED_FIXTURE_PATHS
from .models import sha256_json

GITATTRIBUTES = b"* text eol=lf\n"
GITIGNORE = b"__pycache__/\n*.py[cod]\n"
SOURCE_PRE = (
    b"def add(left: int, right: int) -> int:\n"
    b'    """Return the sum of two integers."""\n'
    b"\n"
    b"    return left - right\n"
)
SOURCE_POST = (
    b"def add(left: int, right: int) -> int:\n"
    b'    """Return the sum of two integers."""\n'
    b"\n"
    b"    return left + right\n"
)
SOURCE_TAMPERED = (
    b"def add(left: int, right: int) -> int:\n"
    b'    """Return the sum of two integers."""\n'
    b"\n"
    b"    return left * right\n"
)
TEST_SOURCE = (
    b"import unittest\n"
    b"\n"
    b"from src.calculator import add\n"
    b"\n"
    b"\n"
    b"class CalculatorTests(unittest.TestCase):\n"
    b"    def test_adds_two_integers(self) -> None:\n"
    b"        self.assertEqual(add(2, 3), 5)\n"
    b"\n"
    b"\n"
    b'if __name__ == "__main__":\n'
    b"    unittest.main()\n"
)
PATCH = (
    b"diff --git a/src/calculator.py b/src/calculator.py\n"
    b"--- a/src/calculator.py\n"
    b"+++ b/src/calculator.py\n"
    b"@@ -1,4 +1,4 @@\n"
    b" def add(left: int, right: int) -> int:\n"
    b'     """Return the sum of two integers."""\n'
    b" \n"
    b"-    return left - right\n"
    b"+    return left + right\n"
)

FILES_PRE: dict[str, bytes] = {
    ".gitattributes": GITATTRIBUTES,
    ".gitignore": GITIGNORE,
    "fix.patch": PATCH,
    "src/__init__.py": b"",
    "src/calculator.py": SOURCE_PRE,
    "tests/__init__.py": b"",
    "tests/test_calculator.py": TEST_SOURCE,
}


def _git_environment(root: Path) -> dict[str, str]:
    environment = os.environ.copy()
    private_home = root.parent / ".git-home"
    private_home.mkdir(exist_ok=True)
    environment.update(
        {
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_CONFIG_NOSYSTEM": "1",
            "HOME": str(private_home),
            "USERPROFILE": str(private_home),
        }
    )
    return environment


def _run_git(root: Path, *arguments: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *arguments],
        cwd=root,
        env=_git_environment(root),
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=True,
    )


def create_fixture(root: Path) -> None:
    """Create and commit the exact registered synthetic repository."""

    if any(root.iterdir()):
        raise ValueError("coding fixture root must be empty")
    for relative, content in FILES_PRE.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    _run_git(root, "init", "-q")
    _run_git(root, "config", "core.autocrlf", "false")
    _run_git(root, "config", "core.safecrlf", "true")
    _run_git(root, "add", "--", *REGISTERED_FIXTURE_PATHS)
    _run_git(
        root,
        "-c",
        "user.name=effect-witness-fixture",
        "-c",
        "user.email=effect-witness-fixture.invalid",
        "commit",
        "-q",
        "-m",
        "registered baseline",
    )


def snapshot(root: Path) -> dict[str, Any]:
    """Return a fail-closed projection of the exact registered fixture files."""

    entries: list[dict[str, Any]] = []
    for relative in REGISTERED_FIXTURE_PATHS:
        path = root / relative
        metadata = path.stat(follow_symlinks=False)
        if not path.is_file() or _is_link_or_reparse(path):
            raise RuntimeError("registered coding fixture path is not a regular file")
        content = path.read_bytes()
        after = path.stat(follow_symlinks=False)
        before_version = (
            metadata.st_dev,
            metadata.st_ino,
            metadata.st_size,
            metadata.st_mtime_ns,
        )
        after_version = (
            after.st_dev,
            after.st_ino,
            after.st_size,
            after.st_mtime_ns,
        )
        if before_version != after_version:
            raise RuntimeError("registered coding fixture changed during observation")
        entries.append(
            {
                "bytes": len(content),
                "kind": "file",
                "path": relative,
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )
    entries.sort(key=lambda item: item["path"])
    return {"entries": entries, "tree_sha256": sha256_json(entries)}


def changed_paths(root: Path) -> list[str]:
    result = _run_git(root, "diff", "--name-only", "--no-ext-diff", "--")
    paths = [line.strip().replace("\\", "/") for line in result.stdout.splitlines()]
    if any(path not in REGISTERED_FIXTURE_PATHS for path in paths):
        raise RuntimeError("coding fixture contains an unregistered tracked change")
    return paths


def validate_fixture(root: Path) -> dict[str, Any]:
    for relative in ("src/__pycache__", "tests/__pycache__"):
        cache = root / relative
        if cache.exists():
            if not cache.is_dir() or _is_link_or_reparse(cache):
                raise RuntimeError("coding fixture bytecode cache is not ordinary")
            shutil.rmtree(cache)
    environment = os.environ.copy()
    environment.update(
        {
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONHASHSEED": "0",
        }
    )
    result = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"],
        cwd=root,
        env=environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=30,
        check=False,
    )
    return {
        "output_included": False,
        "returncode": result.returncode,
        "status": "PASSED" if result.returncode == 0 else "FAILED",
    }


def tamper_fixture(root: Path) -> None:
    (root / "src" / "calculator.py").write_bytes(SOURCE_TAMPERED)


def main(argv: list[str] | None = None) -> int:
    arguments = sys.argv[1:] if argv is None else argv
    if arguments != ["submit"]:
        raise SystemExit("expected only the registered submit command")
    print("COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT")
    print("registered synthetic fixture complete")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
