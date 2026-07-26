from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import privacy_scan
from scripts.privacy_scan import PrivacyScanError, main, scan

_EMAIL_FIXTURE = "person" + chr(64) + "example.com"


def _locations(findings) -> list[tuple[str, int, str]]:
    return [(item.kind, item.line, item.path) for item in findings]


def test_nul_and_non_utf8_files_are_redacted_structured_failures(tmp_path) -> None:
    (tmp_path / "nul.bin").write_bytes(b"safe\x00payload")
    (tmp_path / "legacy.bin").write_bytes(b"\xff\xfe")

    assert _locations(scan(tmp_path)) == [
        ("non_utf8_file_unscanned", 0, "<redacted-path>"),
        ("nul_bytes_unscanned", 0, "<redacted-path>"),
    ]


def test_oversized_utf8_file_is_a_redacted_structured_failure(
    tmp_path,
    monkeypatch,
) -> None:
    (tmp_path / "large.txt").write_text(
        "x" * (2 * 1024 * 1024 + 1),
        encoding="utf-8",
    )
    monkeypatch.setattr(os, "read", lambda *_args: pytest.fail("unbounded read"))

    assert _locations(scan(tmp_path)) == [
        ("oversized_utf8_text_unscanned", 0, "<redacted-path>")
    ]


def test_sensitive_filename_is_scanned_and_redacted(tmp_path) -> None:
    sensitive_name = _EMAIL_FIXTURE + ".txt"
    (tmp_path / sensitive_name).write_text("safe\n", encoding="utf-8")

    findings = scan(tmp_path)

    assert _locations(findings) == [("path_email_address", 0, "<redacted-path>")]
    assert sensitive_name not in repr(findings)


def test_denylisted_relative_path_is_scanned_and_redacted(tmp_path) -> None:
    sensitive_part = "internal" + "-alias"
    repository = tmp_path / "repository"
    nested = repository / sensitive_part
    nested.mkdir(parents=True)
    (nested / "note.txt").write_text("safe\n", encoding="utf-8")
    denylist = tmp_path / "denylist.txt"
    denylist.write_text(f"{sensitive_part}\n", encoding="utf-8")

    findings = scan(
        repository,
        denylist_file=denylist,
        require_denylist=True,
    )

    assert _locations(findings) == [("path_denylist_literal_1", 0, "<redacted-path>")]
    assert sensitive_part not in repr(findings)


@pytest.mark.parametrize(
    "directory_name",
    [".venv", "build", "dist", "__pycache__", "pytest-cache-files-hidden"],
)
def test_formerly_skipped_directories_are_scanned(
    tmp_path,
    directory_name: str,
) -> None:
    directory = tmp_path / directory_name
    directory.mkdir()
    (directory / "note.txt").write_text(
        _EMAIL_FIXTURE + "\n",
        encoding="utf-8",
    )

    assert _locations(scan(tmp_path)) == [("email_address", 1, "<redacted-path>")]


def test_verified_root_git_directory_is_the_only_skipped_directory(tmp_path) -> None:
    metadata = tmp_path / ".git"
    metadata.mkdir()
    (metadata / "private.txt").write_text(
        _EMAIL_FIXTURE + "\n",
        encoding="utf-8",
    )
    nested = tmp_path / "nested" / ".git"
    nested.mkdir(parents=True)
    (nested / "private.txt").write_text(
        _EMAIL_FIXTURE + "\n",
        encoding="utf-8",
    )

    assert _locations(scan(tmp_path)) == [("email_address", 1, "<redacted-path>")]


@pytest.mark.skipif(
    not getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0),
    reason="platform has no Windows reparse attribute",
)
@pytest.mark.parametrize("target_name", [None, ".git"])
def test_root_and_root_git_reparse_points_are_rejected_without_traversal(
    tmp_path,
    monkeypatch,
    target_name,
) -> None:
    target = tmp_path
    if target_name is not None:
        target = tmp_path / target_name
        target.mkdir()
    original = Path.lstat
    reparse_metadata = SimpleNamespace(
        st_mode=stat.S_IFDIR,
        st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT,
    )

    def fake_lstat(path: Path):
        if path == target:
            return reparse_metadata
        return original(path)

    monkeypatch.setattr(Path, "lstat", fake_lstat)
    with pytest.raises(PrivacyScanError):
        scan(tmp_path)


def test_required_denylist_rejects_missing_empty_and_repository_local(
    tmp_path,
) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    with pytest.raises(PrivacyScanError):
        scan(repository, require_denylist=True)

    empty = tmp_path / "empty.txt"
    empty.write_text("# comment only\n", encoding="utf-8")
    with pytest.raises(PrivacyScanError):
        scan(repository, denylist_file=empty, require_denylist=True)

    local = repository / "denylist.txt"
    local.write_text("private-name\n", encoding="utf-8")
    with pytest.raises(PrivacyScanError):
        scan(repository, denylist_file=local, require_denylist=True)


def test_required_denylist_rejects_nul_non_utf8_and_oversized(tmp_path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    nul = tmp_path / "nul.txt"
    nul.write_bytes(b"private\x00name")
    legacy = tmp_path / "legacy.txt"
    legacy.write_bytes(b"\xff\xfe")
    oversized = tmp_path / "oversized.txt"
    oversized.write_bytes(b"x" * (2 * 1024 * 1024 + 1))

    for denylist in (nul, legacy, oversized):
        with pytest.raises(PrivacyScanError):
            scan(
                repository,
                denylist_file=denylist,
                require_denylist=True,
            )


def test_main_sanitizes_all_ordinary_errors(tmp_path, capsys) -> None:
    sensitive_root = tmp_path / "private-person-name.txt"
    sensitive_root.write_text("safe\n", encoding="utf-8")

    assert main([str(sensitive_root), "--require-denylist"]) == 2
    captured = capsys.readouterr()
    report = json.loads(captured.out)
    assert report == {
        "error_code": "privacy_scan_failed",
        "matched_values_redacted": True,
        "status": "error",
    }
    assert str(sensitive_root) not in captured.out
    assert str(sensitive_root) not in captured.err


def test_optional_denylist_mode_reports_that_it_is_not_enforced(
    tmp_path,
    capsys,
) -> None:
    (tmp_path / "safe.txt").write_text("safe\n", encoding="utf-8")

    assert main([str(tmp_path)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["denylist_enforcement"] == "optional_not_enforced"
    assert report["denylist_provided"] is False


@pytest.mark.parametrize(
    ("content", "kind"),
    [
        ("github_" + "pat_" + "A" * 30, "github_token"),
        (
            chr(92) * 2 + "server" + chr(92) + "share" + chr(92) + "private.txt",
            "unc_path",
        ),
        ("~" + "/private/file", "tilde_home_path"),
        ("/" + "root/private/file", "absolute_posix_home"),
        ("/mnt/" + "c/" + "Us" + "ers/person/private", "wsl_windows_home"),
        (
            "-" * 5 + "BEGIN " + "ENCRYPTED " + "PRIVATE KEY" + "-" * 5,
            "private_key",
        ),
        ("10" + ".20.30.40", "non_loopback_ipv4"),
        ("192" + ".168.1.8", "non_loopback_ipv4"),
    ],
)
def test_high_risk_patterns_are_detected(tmp_path, content: str, kind: str) -> None:
    (tmp_path / "note.txt").write_text(content + "\n", encoding="utf-8")

    assert _locations(scan(tmp_path)) == [(kind, 1, "<redacted-path>")]


def test_loopback_ipv4_is_not_reported(tmp_path) -> None:
    (tmp_path / "note.txt").write_text("127.0.0.1\n", encoding="utf-8")

    assert scan(tmp_path) == []


def test_lstat_failure_is_never_silently_skipped(tmp_path, monkeypatch) -> None:
    target = tmp_path / "note.txt"
    target.write_text("safe\n", encoding="utf-8")
    original = Path.lstat

    def fail_target(path: Path):
        if path == target:
            raise PermissionError
        return original(path)

    monkeypatch.setattr(Path, "lstat", fail_target)
    with pytest.raises(PrivacyScanError):
        scan(tmp_path)


def test_non_regular_entry_is_rejected(tmp_path, monkeypatch) -> None:
    target = tmp_path / "note.txt"
    target.write_text("safe\n", encoding="utf-8")
    original = privacy_scan._lstat_checked

    def fake_mode(path: Path):
        metadata = original(path)
        if path == target:
            values = list(metadata)
            values[0] = (values[0] & ~0o170000) | 0o010000
            return os.stat_result(values)
        return metadata

    monkeypatch.setattr(privacy_scan, "_lstat_checked", fake_mode)
    with pytest.raises(PrivacyScanError):
        scan(tmp_path)


def test_file_change_during_read_is_rejected(tmp_path, monkeypatch) -> None:
    target = tmp_path / "note.txt"
    target.write_text("safe\n", encoding="utf-8")
    original_fstat = os.fstat
    calls = 0

    def changed_fstat(descriptor: int):
        nonlocal calls
        metadata = original_fstat(descriptor)
        calls += 1
        if calls == 2:
            values = list(metadata)
            values[8] = metadata.st_mtime + 1
            return os.stat_result(values)
        return metadata

    monkeypatch.setattr(os, "fstat", changed_fstat)
    with pytest.raises(PrivacyScanError):
        scan(tmp_path)


@pytest.mark.skipif(
    not hasattr(os, "symlink"),
    reason="platform has no symlink support",
)
def test_root_and_file_symlinks_are_rejected(tmp_path) -> None:
    repository = tmp_path / "repository"
    repository.mkdir()
    target = repository / "target.txt"
    target.write_text("safe\n", encoding="utf-8")
    file_link = repository / "link.txt"
    root_link = tmp_path / "root-link"
    try:
        file_link.symlink_to(target)
        root_link.symlink_to(repository, target_is_directory=True)
    except OSError:
        pytest.skip("symlink creation is not permitted")

    with pytest.raises(PrivacyScanError):
        scan(repository)
    with pytest.raises(PrivacyScanError):
        scan(root_link)
