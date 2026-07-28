from __future__ import annotations

import json
from pathlib import Path

import pytest

import effect_witness.coding_dependencies as dependencies
from effect_witness.coding_dependencies import (
    MINI_SWE_AGENT_DEVELOPMENT_STATUS,
    MINI_SWE_AGENT_LICENSE,
    MINI_SWE_AGENT_PACKAGE,
    MINI_SWE_AGENT_PYTHON_REQUIRES,
    MINI_SWE_AGENT_VERSION,
    MINI_SWE_AGENT_WHEEL_BYTES,
    MINI_SWE_AGENT_WHEEL_FILENAME,
    MINI_SWE_AGENT_WHEEL_SHA256,
    MINI_SWE_AGENT_WHEEL_URL,
    MiniSweWheel,
    verify_mini_swe_wheel,
    verify_wheel_provenance_bytes,
)
from scripts import prepare_coding_agent as preparation


def test_registered_wheel_provenance_is_exact() -> None:
    repository = Path(__file__).resolve().parents[1]
    provenance_path = (
        repository / "integrations" / "mini-swe-agent" / "wheel-provenance.json"
    )

    provenance = verify_wheel_provenance_bytes(provenance_path.read_bytes())

    assert provenance == {
        "development_status": MINI_SWE_AGENT_DEVELOPMENT_STATUS,
        "filename": MINI_SWE_AGENT_WHEEL_FILENAME,
        "license": MINI_SWE_AGENT_LICENSE,
        "package": MINI_SWE_AGENT_PACKAGE,
        "python_requires": MINI_SWE_AGENT_PYTHON_REQUIRES,
        "sha256": MINI_SWE_AGENT_WHEEL_SHA256,
        "size_bytes": MINI_SWE_AGENT_WHEEL_BYTES,
        "url": MINI_SWE_AGENT_WHEEL_URL,
        "version": MINI_SWE_AGENT_VERSION,
    }


def test_runtime_verifier_rejects_wrong_size(tmp_path: Path) -> None:
    wheel = tmp_path / MINI_SWE_AGENT_WHEEL_FILENAME
    wheel.write_bytes(b"not-the-registered-wheel")

    with pytest.raises(ValueError, match="size differs"):
        verify_mini_swe_wheel(wheel)


def test_runtime_verifier_rejects_wrong_hash_at_registered_size(
    tmp_path: Path,
) -> None:
    wheel = tmp_path / MINI_SWE_AGENT_WHEEL_FILENAME
    wheel.write_bytes(b"x" * MINI_SWE_AGENT_WHEEL_BYTES)

    with pytest.raises(ValueError, match="digest differs"):
        verify_mini_swe_wheel(wheel)


def test_preparation_rejects_preexisting_output_before_download(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output = tmp_path / "coding-agent"
    output.mkdir()
    called = False

    def unexpected_download(_destination: Path) -> None:
        nonlocal called
        called = True

    monkeypatch.setattr(
        preparation,
        "_download_registered_wheel",
        unexpected_download,
    )

    with pytest.raises(FileExistsError, match="must be absent"):
        preparation.prepare_mini_swe_wheel(output)

    assert not called
    assert output.is_dir()


def test_preparation_cleans_partial_download_after_failed_verification(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output = tmp_path / "coding-agent"

    def partial_download(destination: Path) -> None:
        destination.write_bytes(b"partial")

    monkeypatch.setattr(
        preparation,
        "_download_registered_wheel",
        partial_download,
    )

    with pytest.raises(ValueError, match="size differs"):
        preparation.prepare_mini_swe_wheel(output)

    assert not output.exists()
    assert list(tmp_path.glob(".coding-agent.staging-*")) == []


def test_preparation_removes_published_output_if_final_recheck_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output = tmp_path / "coding-agent"
    payload = b"network-free-wheel-fixture"
    verifier_calls = 0

    def fixture_download(destination: Path) -> None:
        destination.write_bytes(payload)

    def staged_then_failed_verifier(path: str | Path) -> MiniSweWheel:
        nonlocal verifier_calls
        verifier_calls += 1
        candidate = Path(path)
        if verifier_calls == 2:
            raise ValueError("simulated final verification failure")
        assert candidate.read_bytes() == payload
        return MiniSweWheel(
            path=candidate,
            version=MINI_SWE_AGENT_VERSION,
            sha256=MINI_SWE_AGENT_WHEEL_SHA256,
            bytes=MINI_SWE_AGENT_WHEEL_BYTES,
        )

    monkeypatch.setattr(
        preparation,
        "_download_registered_wheel",
        fixture_download,
    )
    monkeypatch.setattr(
        preparation,
        "verify_mini_swe_wheel",
        staged_then_failed_verifier,
    )

    with pytest.raises(ValueError, match="final verification"):
        preparation.prepare_mini_swe_wheel(output)

    assert verifier_calls == 2
    assert not output.exists()
    assert list(tmp_path.glob(".coding-agent.staging-*")) == []


def test_failure_report_contains_no_output_path(
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
) -> None:
    output = tmp_path / "sensitive-local-path"
    output.mkdir()

    assert preparation.main(["--output-dir", str(output)]) == 1

    report = capsys.readouterr().out
    parsed = json.loads(report)
    assert parsed == {"error_type": "FileExistsError", "prepared": False}
    assert str(tmp_path) not in report


def test_provenance_rejects_boolean_size_coercion() -> None:
    provenance = dependencies.expected_mini_swe_provenance()
    provenance["size_bytes"] = True

    with pytest.raises(ValueError, match="differs from registration"):
        verify_wheel_provenance_bytes(
            json.dumps(provenance, sort_keys=True).encode("utf-8")
        )
