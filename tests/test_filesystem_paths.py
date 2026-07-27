from __future__ import annotations

import ctypes
from pathlib import Path

import pytest

import effect_witness.filesystem_lane as lane_module
import effect_witness.filesystem_paths as paths_module
from effect_witness.filesystem_lane import _write_manifest
from effect_witness.filesystem_paths import (
    create_owned_directory,
    create_staging_directory,
    ensure_disjoint_paths,
    publish_staging_directory,
    remove_owned_directories,
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


def test_owned_cleanup_retries_a_transient_windows_lock(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    owned = tmp_path / "owned"
    owned.mkdir()
    (owned / "payload.txt").write_text("payload", encoding="utf-8")
    original = paths_module.shutil.rmtree
    calls = 0
    sleeps: list[float] = []

    def flaky_rmtree(path, **kwargs) -> None:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise PermissionError("simulated transient sharing violation")
        original(path, **kwargs)

    monkeypatch.setattr(paths_module.shutil, "rmtree", flaky_rmtree)
    monkeypatch.setattr(paths_module, "_is_retryable_remove_error", lambda _: True)
    monkeypatch.setattr(paths_module.time, "sleep", sleeps.append)

    remove_owned_directory(owned, label="owned test directory")

    assert calls == 2
    assert sleeps == [paths_module._WINDOWS_REMOVE_RETRY_DELAY_SECONDS]
    assert not owned.exists()


def test_owned_cleanup_fails_after_bounded_transient_lock_retries(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    owned = tmp_path / "owned"
    owned.mkdir()
    (owned / "payload.txt").write_text("payload", encoding="utf-8")
    calls = 0

    def locked_rmtree(_path, **_kwargs) -> None:
        nonlocal calls
        calls += 1
        raise PermissionError("simulated persistent sharing violation")

    monkeypatch.setattr(paths_module.shutil, "rmtree", locked_rmtree)
    monkeypatch.setattr(paths_module, "_is_retryable_remove_error", lambda _: True)
    monkeypatch.setattr(paths_module.time, "sleep", lambda _: None)

    with pytest.raises(RuntimeError, match=r"cannot remove .+ \(PermissionError\)"):
        remove_owned_directory(owned, label="owned test directory")

    assert calls == paths_module._REMOVE_ATTEMPTS
    assert owned.exists()


@pytest.mark.parametrize(
    ("first_suffix", "second_suffix"),
    (
        (("output",), ("output",)),
        (("output",), ("output", "work")),
        (("output", "artifact"), ("output",)),
    ),
)
def test_disjoint_paths_reject_overlap_without_creating_directories(
    tmp_path: Path,
    first_suffix: tuple[str, ...],
    second_suffix: tuple[str, ...],
) -> None:
    first = tmp_path.joinpath(*first_suffix)
    second = tmp_path.joinpath(*second_suffix)

    with pytest.raises(ValueError, match="must not overlap"):
        ensure_disjoint_paths(first, second, label="test directories")

    assert not (tmp_path / "output").exists()


@pytest.mark.skipif(paths_module.os.name != "nt", reason="Windows path alias")
def test_disjoint_paths_reject_extended_length_alias() -> None:
    drive = Path.cwd().drive
    if not drive:
        pytest.skip("Windows drive is unavailable")
    ordinary = Path(drive + paths_module.os.sep) / "effect-witness-boundary" / "output"
    separator = chr(92)
    extended_child = Path(
        f"{separator}{separator}?{separator}{ordinary}{separator}work"
    )

    with pytest.raises(ValueError, match="must not overlap"):
        ensure_disjoint_paths(ordinary, extended_child, label="test directories")


@pytest.mark.skipif(paths_module.os.name != "nt", reason="Windows volume alias")
def test_disjoint_paths_reject_volume_guid_alias(tmp_path: Path) -> None:
    volume_name = ctypes.create_unicode_buffer(1024)
    get_volume_name = ctypes.windll.kernel32.GetVolumeNameForVolumeMountPointW
    if not get_volume_name(tmp_path.anchor, volume_name, len(volume_name)):
        pytest.skip("volume GUID is unavailable")
    relative_parent = tmp_path.parent.relative_to(tmp_path.anchor)
    ordinary = tmp_path.parent / "volume-alias-boundary"
    volume_child = (
        Path(volume_name.value) / relative_parent / "volume-alias-boundary" / "work"
    )

    with pytest.raises(ValueError, match="must not overlap"):
        ensure_disjoint_paths(ordinary, volume_child, label="test directories")


def test_disjoint_paths_reject_symlink_ancestor_alias(tmp_path: Path) -> None:
    real = tmp_path / "real"
    dependency = real / "dependency"
    dependency.mkdir(parents=True)
    alias = tmp_path / "alias"
    try:
        alias.symlink_to(real, target_is_directory=True)
    except OSError:
        pytest.skip("directory symlink creation is unavailable")

    with pytest.raises(ValueError, match="must not overlap"):
        ensure_disjoint_paths(
            alias / "dependency",
            dependency / "output",
            label="test directories",
        )


def test_multi_cleanup_attempts_every_target(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()
    original = paths_module.remove_owned_directory
    attempted: list[Path] = []

    def partially_failing_cleanup(path: Path, *, label: str) -> None:
        attempted.append(path)
        if path == first:
            raise RuntimeError(label)
        original(path, label=label)

    monkeypatch.setattr(
        paths_module,
        "remove_owned_directory",
        partially_failing_cleanup,
    )

    with pytest.raises(RuntimeError, match="remain after cleanup"):
        remove_owned_directories([(first, "first"), (second, "second")])

    assert attempted == [first, second]
    assert first.exists()
    assert not second.exists()


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
