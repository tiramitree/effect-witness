from __future__ import annotations

from pathlib import Path

import pytest

import effect_witness.filesystem_lane as lane_module
import effect_witness.filesystem_paths as paths_module
from effect_witness.filesystem_lane import _write_manifest
from effect_witness.filesystem_paths import (
    create_owned_directory,
    create_staging_directory,
    publish_staging_directory,
    remove_owned_directory,
)


def test_staging_requires_absent_final_directory(tmp_path: Path) -> None:
    final = tmp_path / "artifact"
    final.mkdir()

    with pytest.raises(FileExistsError, match="must be absent"):
        create_staging_directory(final, label="artifact output directory")


def test_new_directory_rejects_reparse_parent(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    unsafe_parent = tmp_path / "unsafe"
    unsafe_parent.mkdir()
    original = paths_module._is_link_or_reparse
    monkeypatch.setattr(
        paths_module,
        "_is_link_or_reparse",
        lambda path: path == unsafe_parent or original(path),
    )

    with pytest.raises(RuntimeError, match="parent is not an ordinary directory"):
        create_owned_directory(
            unsafe_parent / "work",
            label="filesystem lane work directory",
        )

    assert not (unsafe_parent / "work").exists()


def test_staging_publish_is_same_parent_and_complete(tmp_path: Path) -> None:
    final, staging = create_staging_directory(
        tmp_path / "artifact",
        label="artifact output directory",
    )
    (staging / "complete.txt").write_bytes(b"complete")

    publish_staging_directory(
        staging,
        final,
        label="artifact output directory",
    )

    assert not staging.exists()
    assert (final / "complete.txt").read_bytes() == b"complete"
    remove_owned_directory(final, label="artifact output directory")


def test_owned_cleanup_retries_a_disappeared_child(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    owned = tmp_path / "owned"
    owned.mkdir()
    (owned / "payload.txt").write_text("payload", encoding="utf-8")
    original = paths_module.shutil.rmtree
    calls = 0

    def flaky_rmtree(path, **kwargs) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise FileNotFoundError("simulated disappearing child")
        original(path, **kwargs)

    monkeypatch.setattr(paths_module.shutil, "rmtree", flaky_rmtree)

    remove_owned_directory(owned, label="owned test directory")

    assert calls == 2
    assert not owned.exists()


def test_manifest_writer_rejects_reparse_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    output = tmp_path / "staging"
    unsafe = output / "results"
    unsafe.mkdir(parents=True)
    (unsafe / "result.json").write_text("{}", encoding="utf-8")
    original = lane_module._is_link_or_reparse
    monkeypatch.setattr(
        lane_module,
        "_is_link_or_reparse",
        lambda path: path == unsafe or original(path),
    )

    with pytest.raises(RuntimeError, match="unsafe directory"):
        _write_manifest(output)

    assert not (output / "manifest.sha256").exists()
