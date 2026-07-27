from __future__ import annotations

import os
from pathlib import Path

import effect_witness.artifact as artifact_module
from effect_witness.artifact import verify_artifact


def test_oversized_file_is_rejected_before_open(monkeypatch, tmp_path) -> None:
    artifact = tmp_path / "artifact"
    artifact.mkdir()
    oversized = artifact / "oversized.bin"
    oversized.write_bytes(b"x" * (artifact_module._MAX_FILE_BYTES + 1))
    (artifact / "manifest.sha256").write_text(
        f"{'0' * 64}  oversized.bin\n",
        encoding="utf-8",
        newline="\n",
    )
    real_open = os.open
    oversized_opened = False

    def guarded_open(path, flags, *args):
        nonlocal oversized_opened
        if Path(path) == oversized:
            oversized_opened = True
            raise AssertionError("oversized artifact file was opened")
        return real_open(path, flags, *args)

    monkeypatch.setattr(artifact_module.os, "open", guarded_open)

    report = verify_artifact(artifact)

    assert report["verified"] is False
    assert "artifact file exceeds size limit: oversized.bin" in report["errors"]
    assert oversized_opened is False
    assert "artifact verification aborted (AssertionError)" not in report["errors"]


def test_semantic_verification_uses_snapshot_only(
    monkeypatch,
    schema_v2_artifact: Path,
) -> None:
    artifact = schema_v2_artifact

    def unexpected_path_read(*_args, **_kwargs):
        raise AssertionError("verifier reread an artifact path")

    monkeypatch.setattr(Path, "read_bytes", unexpected_path_read)
    monkeypatch.setattr(Path, "read_text", unexpected_path_read)
    monkeypatch.setattr(artifact_module.ET, "parse", unexpected_path_read)

    report = verify_artifact(artifact)

    assert report["verified"] is True
    assert report["errors"] == []


def test_replacement_between_stat_and_open_fails_closed(
    monkeypatch,
    tmp_path,
    schema_v2_artifact: Path,
) -> None:
    artifact = schema_v2_artifact
    target = artifact / "summary.json"
    replacement = tmp_path / "replacement.json"
    replacement.write_bytes(target.read_bytes())
    real_open = os.open
    replaced = False

    def replacing_open(path, flags, *args):
        nonlocal replaced
        if Path(path) == target and not replaced:
            replaced = True
            os.replace(replacement, target)
        return real_open(path, flags, *args)

    monkeypatch.setattr(artifact_module.os, "open", replacing_open)

    report = verify_artifact(artifact)

    assert report["verified"] is False
    assert replaced is True
    assert (
        "artifact file changed before snapshot read: summary.json" in report["errors"]
    )
    assert not any("Traceback" in error for error in report["errors"])


def test_change_during_read_fails_closed(
    monkeypatch,
    schema_v2_artifact: Path,
) -> None:
    artifact = schema_v2_artifact
    target = artifact / "summary.json"
    target_before = target.stat(follow_symlinks=False)
    real_fstat = os.fstat
    real_read = os.read
    changed = False

    def changing_read(descriptor, length):
        nonlocal changed
        chunk = real_read(descriptor, length)
        if not changed and os.path.samestat(
            real_fstat(descriptor),
            target.stat(follow_symlinks=False),
        ):
            changed = True
            os.utime(
                target,
                ns=(
                    target_before.st_atime_ns,
                    target_before.st_mtime_ns + 2_000_000_000,
                ),
            )
        return chunk

    monkeypatch.setattr(artifact_module.os, "read", changing_read)

    report = verify_artifact(artifact)

    assert report["verified"] is False
    assert changed is True
    assert (
        "artifact file changed during snapshot read: summary.json" in report["errors"]
    )
    assert not any("Traceback" in error for error in report["errors"])


def test_total_limit_prevents_loading_past_budget(monkeypatch, tmp_path) -> None:
    artifact = tmp_path / "artifact"
    artifact.mkdir()
    (artifact / "a.bin").write_bytes(b"a" * 6)
    (artifact / "b.bin").write_bytes(b"b" * 6)
    monkeypatch.setattr(artifact_module, "_MAX_FILE_BYTES", 10)
    monkeypatch.setattr(artifact_module, "_MAX_TOTAL_BYTES", 10)
    real_open = os.open
    opened: list[str] = []

    def recording_open(path, flags, *args):
        opened.append(Path(path).name)
        return real_open(path, flags, *args)

    monkeypatch.setattr(artifact_module.os, "open", recording_open)
    errors: list[str] = []

    files, snapshot = artifact_module._artifact_snapshot(artifact, errors)

    assert files == {"a.bin", "b.bin"}
    assert snapshot == {"a.bin": b"a" * 6}
    assert errors == ["artifact exceeds total size limit"]
    assert opened == ["a.bin"]
