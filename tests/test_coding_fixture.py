from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from effect_witness.coding_fixture import (
    SOURCE_POST,
    SOURCE_TAMPERED,
    create_fixture,
    validate_fixture,
)


def test_validation_discards_same_size_stale_bytecode(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    create_fixture(workspace)
    source = workspace / "src" / "calculator.py"
    source.write_bytes(SOURCE_POST)
    source_mtime = source.stat().st_mtime_ns
    bytecode_environment = os.environ.copy()
    bytecode_environment.pop("PYTHONDONTWRITEBYTECODE", None)
    first = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"],
        cwd=workspace,
        env=bytecode_environment,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert first.returncode == 0
    assert (workspace / "src" / "__pycache__").is_dir()

    source.write_bytes(SOURCE_TAMPERED)
    os.utime(source, ns=(source_mtime, source_mtime))

    assert validate_fixture(workspace) == {
        "output_included": False,
        "returncode": 1,
        "status": "FAILED",
    }
    assert not (workspace / "src" / "__pycache__").exists()
    assert not (workspace / "tests" / "__pycache__").exists()
