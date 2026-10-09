from __future__ import annotations

import importlib.metadata
import re
import sys
from pathlib import Path

import pytest

import effect_witness.langgraph_constraints as constraints_module
from effect_witness.langgraph_constraints import verify_python_constraints


def _constraint_path() -> Path:
    return (
        Path(__file__).resolve().parents[1]
        / "integrations"
        / "langgraph"
        / "constraints.txt"
    )


def _registered_versions() -> dict[str, str]:
    versions: dict[str, str] = {}
    for line in _constraint_path().read_text(encoding="utf-8").splitlines():
        if line.startswith("#"):
            continue
        requirement, _, marker = line.partition(" ; ")
        name, version = requirement.split("==", 1)
        if marker and sys.platform != "win32":
            continue
        versions[re.sub(r"[-_.]+", "-", name).lower()] = version
    return versions


def test_constraint_gate_checks_every_applicable_registration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    versions = _registered_versions()
    monkeypatch.setattr(
        constraints_module.importlib.metadata,
        "version",
        versions.__getitem__,
    )

    report = verify_python_constraints(_constraint_path())

    assert report == {
        "applicable_package_count": len(versions),
        "registered_package_count": 58,
    }


def test_constraint_gate_rejects_byte_drift(tmp_path: Path) -> None:
    drifted = tmp_path / "constraints.txt"
    drifted.write_bytes(_constraint_path().read_bytes() + b"# drift\n")

    with pytest.raises(RuntimeError, match="bytes differ from registration"):
        verify_python_constraints(drifted)


def test_constraint_gate_rejects_pre_security_refresh_lock(tmp_path: Path) -> None:
    historical = tmp_path / "historical.txt"
    historical.write_bytes(
        _constraint_path()
        .read_bytes()
        .replace(
            b"langgraph-checkpoint-sqlite==3.1.1",
            b"langgraph-checkpoint-sqlite==3.1.0",
        )
    )
    with pytest.raises(RuntimeError, match="bytes differ from registration"):
        verify_python_constraints(historical)


def test_constraint_gate_rejects_missing_applicable_distribution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing(_name: str) -> str:
        raise importlib.metadata.PackageNotFoundError

    monkeypatch.setattr(
        constraints_module.importlib.metadata,
        "version",
        missing,
    )

    with pytest.raises(RuntimeError, match="distribution is unavailable"):
        verify_python_constraints(_constraint_path())
