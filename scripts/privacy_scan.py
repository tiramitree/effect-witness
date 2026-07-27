"""Fail-closed scan for common public-repository privacy hazards."""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import unicodedata
from dataclasses import dataclass
from pathlib import Path

_MAX_TEXT_BYTES = 2 * 1024 * 1024
_MAX_DENYLIST_BYTES = 2 * 1024 * 1024
_REDACTED_PATH = "<redacted-path>"
_READ_CHUNK_BYTES = 64 * 1024
_IPV4_OCTET = r"(?:25[0-5]|2[0-4]\d|1?\d?\d)"
_PATTERNS = {
    "absolute_posix_home": re.compile(
        r"(?i)(?<![\w.])(?:/(?:home|users)/[^/\s]+(?:/|$)|/root(?:/|$))"
    ),
    "wsl_windows_home": re.compile(
        r"(?i)(?<![\w.])/mnt/[a-z]/"
        r"users/[^/\s]+(?:/|$)"
    ),
    "absolute_windows_path": re.compile(r"(?i)(?<![\w.])[a-z]:[\\/]"),
    "unc_path": re.compile(
        r"(?i)(?<![\\\w])(?:\\\\\?\\UNC\\|\\\\)"
        r"[^\\/\s]+\\[^\\/\s]+(?:\\|$)"
    ),
    "tilde_home_path": re.compile(r"(?<![\w.])~[\\/]"),
    "email_address": re.compile(
        r"(?i)\b[a-z0-9.!#$%&'*+/=?^_`{|}~-]+"
        r"@[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?"
        r"(?:\.[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?)*"
        r"\.(?:[a-z]{2,63}|xn--[a-z0-9-]{2,59})\b"
    ),
    "github_token": re.compile(
        r"\b(?:(?:gh[oprsu]_[A-Za-z0-9]{20,})|"
        r"(?:github_pat_[A-Za-z0-9_]{20,}))\b"
    ),
    "private_key": re.compile(
        r"(?i)-----BEGIN (?:ENCRYPTED |RSA |DSA |EC |OPENSSH )?PRIVATE KEY-----"
    ),
    "non_loopback_ipv4": re.compile(
        rf"(?<![\d.])(?!127(?:\.{_IPV4_OCTET}){{3}}(?![\d.]))"
        rf"(?:{_IPV4_OCTET}\.){{3}}{_IPV4_OCTET}(?![\d.])"
    ),
    "phone_like": re.compile(
        r"(?<![a-zA-Z0-9])(?:\+?86[- ]?)?1[3-9]\d{9}(?![a-zA-Z0-9])"
    ),
}


class PrivacyScanError(RuntimeError):
    """A deliberately path-free fatal scan error."""


class _OversizedFile(PrivacyScanError):
    """A regular file exceeded its bounded text-scan size."""


@dataclass(frozen=True)
class Finding:
    kind: str
    line: int
    path: str = _REDACTED_PATH


def _normalize(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold()


def _is_reparse(metadata: os.stat_result) -> bool:
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    attributes = getattr(metadata, "st_file_attributes", 0)
    return bool(reparse_flag and attributes & reparse_flag)


def _lstat_checked(path: Path) -> os.stat_result:
    try:
        metadata = path.lstat()
    except OSError as error:
        raise PrivacyScanError("filesystem metadata unavailable") from error
    if stat.S_ISLNK(metadata.st_mode) or _is_reparse(metadata):
        raise PrivacyScanError("link or reparse point is not allowed")
    return metadata


def _identity(metadata: os.stat_result) -> tuple[int, int, int, int, int, int]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        stat.S_IFMT(metadata.st_mode),
        metadata.st_size,
        metadata.st_mtime_ns,
        getattr(metadata, "st_file_attributes", 0),
    )


def _directory_identity(metadata: os.stat_result) -> tuple[int, int, int, int]:
    return (
        metadata.st_dev,
        metadata.st_ino,
        metadata.st_mtime_ns,
        getattr(metadata, "st_file_attributes", 0),
    )


def _absolute_without_resolving(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _verified_root(root: Path) -> tuple[Path, os.stat_result]:
    absolute = _absolute_without_resolving(root)
    metadata = _lstat_checked(absolute)
    if not stat.S_ISDIR(metadata.st_mode):
        raise PrivacyScanError("scan root is not a regular directory")
    try:
        resolved = absolute.resolve(strict=True)
    except OSError as error:
        raise PrivacyScanError("scan root cannot be resolved") from error
    if os.path.normcase(os.fspath(resolved)) != os.path.normcase(os.fspath(absolute)):
        raise PrivacyScanError("scan root traverses a link or reparse point")
    return absolute, metadata


def _verify_directory_unchanged(path: Path, expected: os.stat_result) -> None:
    current = _lstat_checked(path)
    if not stat.S_ISDIR(current.st_mode):
        raise PrivacyScanError("directory type changed during scan")
    if _directory_identity(current) != _directory_identity(expected):
        raise PrivacyScanError("directory changed during scan")


def _candidate_files(root: Path) -> list[tuple[Path, os.stat_result]]:
    candidates: list[tuple[Path, os.stat_result]] = []
    visited: set[tuple[int, int]] = set()

    def visit(directory: Path, expected: os.stat_result, *, is_root: bool) -> None:
        directory_key = (expected.st_dev, expected.st_ino)
        if directory_key in visited:
            raise PrivacyScanError("directory identity repeated during scan")
        visited.add(directory_key)
        try:
            with os.scandir(directory) as entries:
                ordered = sorted(entries, key=lambda item: item.name)
        except OSError as error:
            raise PrivacyScanError("repository traversal failed") from error

        for entry in ordered:
            path = Path(entry.path)
            metadata = _lstat_checked(path)
            if is_root and entry.name == ".git":
                if not (
                    stat.S_ISDIR(metadata.st_mode) or stat.S_ISREG(metadata.st_mode)
                ):
                    raise PrivacyScanError(
                        "root metadata entry has an unsupported type"
                    )
                continue
            if stat.S_ISDIR(metadata.st_mode):
                visit(path, metadata, is_root=False)
            elif stat.S_ISREG(metadata.st_mode):
                candidates.append((path, metadata))
            else:
                raise PrivacyScanError("non-regular filesystem entry is not allowed")
        _verify_directory_unchanged(directory, expected)

    root_metadata = _lstat_checked(root)
    if not stat.S_ISDIR(root_metadata.st_mode):
        raise PrivacyScanError("scan root is not a regular directory")
    visit(root, root_metadata, is_root=True)
    return candidates


def _open_flags() -> int:
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0)
    flags |= getattr(os, "O_NOFOLLOW", 0)
    return flags


def _read_regular_file(
    path: Path,
    expected: os.stat_result,
    *,
    max_bytes: int,
) -> bytes:
    try:
        descriptor = os.open(path, _open_flags())
    except OSError as error:
        raise PrivacyScanError("regular file cannot be opened") from error
    try:
        try:
            before = os.fstat(descriptor)
        except OSError as error:
            raise PrivacyScanError("opened file metadata unavailable") from error
        if (
            not stat.S_ISREG(before.st_mode)
            or _is_reparse(before)
            or _identity(before) != _identity(expected)
        ):
            raise PrivacyScanError("file changed before bounded read")
        if before.st_size > max_bytes:
            raise _OversizedFile("regular file exceeds scan limit")

        chunks: list[bytes] = []
        remaining = max_bytes + 1
        while remaining:
            try:
                chunk = os.read(descriptor, min(_READ_CHUNK_BYTES, remaining))
            except OSError as error:
                raise PrivacyScanError("regular file cannot be read") from error
            if not chunk:
                break
            chunks.append(chunk)
            remaining -= len(chunk)
        content = b"".join(chunks)
        if len(content) > max_bytes:
            raise _OversizedFile("regular file exceeds scan limit")

        try:
            after = os.fstat(descriptor)
        except OSError as error:
            raise PrivacyScanError("opened file metadata unavailable") from error
        if _identity(after) != _identity(before) or len(content) != after.st_size:
            raise PrivacyScanError("file changed during bounded read")
        return content
    finally:
        os.close(descriptor)


def _path_is_within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _read_denylist(
    path: Path | None,
    *,
    root: Path,
    required: bool,
) -> list[str]:
    if path is None:
        if required:
            raise PrivacyScanError("required denylist was not provided")
        return []

    absolute = _absolute_without_resolving(path)
    metadata = _lstat_checked(absolute)
    if not stat.S_ISREG(metadata.st_mode):
        raise PrivacyScanError("denylist is not a regular file")
    try:
        resolved = absolute.resolve(strict=True)
    except OSError as error:
        raise PrivacyScanError("denylist cannot be resolved") from error
    if os.path.normcase(os.fspath(resolved)) != os.path.normcase(os.fspath(absolute)):
        raise PrivacyScanError("denylist traverses a link or reparse point")
    if _path_is_within(absolute, root):
        raise PrivacyScanError("denylist must be outside the scan root")
    try:
        content = _read_regular_file(
            absolute,
            metadata,
            max_bytes=_MAX_DENYLIST_BYTES,
        )
    except _OversizedFile as error:
        raise PrivacyScanError("denylist exceeds scan limit") from error
    if b"\0" in content:
        raise PrivacyScanError("denylist contains NUL bytes")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError as error:
        raise PrivacyScanError("denylist is not UTF-8") from error

    values = [
        _normalize(line.strip())
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not values:
        raise PrivacyScanError("denylist has no effective literals")
    if any(len(value) < 3 for value in values):
        raise PrivacyScanError("denylist literals are too short")
    return values


def _match_kinds(value: str, denylist: list[str]) -> list[str]:
    normalized = _normalize(value)
    kinds = [kind for kind, pattern in _PATTERNS.items() if pattern.search(normalized)]
    kinds.extend(
        f"denylist_literal_{index}"
        for index, literal in enumerate(denylist, start=1)
        if literal in normalized
    )
    return kinds


def _full_text_denylist_kinds(text: str, denylist: list[str]) -> list[str]:
    normalized_without_line_breaks = _normalize("".join(text.splitlines()))
    return [
        f"denylist_literal_{index}"
        for index, literal in enumerate(denylist, start=1)
        if literal in normalized_without_line_breaks
    ]


def scan(
    root: Path,
    *,
    denylist_file: Path | None = None,
    require_denylist: bool = False,
) -> list[Finding]:
    """Return redacted locations only; matched sensitive text is never echoed."""

    verified_root, initial_root = _verified_root(root)
    denylist = _read_denylist(
        denylist_file,
        root=verified_root,
        required=require_denylist,
    )
    findings: list[Finding] = []
    for path, metadata in _candidate_files(verified_root):
        relative = path.relative_to(verified_root).as_posix()
        findings.extend(
            Finding(f"path_{kind}", 0) for kind in _match_kinds(relative, denylist)
        )
        try:
            content = _read_regular_file(
                path,
                metadata,
                max_bytes=_MAX_TEXT_BYTES,
            )
        except _OversizedFile:
            findings.append(Finding("oversized_utf8_text_unscanned", 0))
            continue
        if b"\0" in content:
            findings.append(Finding("nul_bytes_unscanned", 0))
            continue
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            findings.append(Finding("non_utf8_file_unscanned", 0))
            continue

        line_denylist_kinds: set[str] = set()
        for line_number, line in enumerate(text.splitlines(), start=1):
            kinds = _match_kinds(line, denylist)
            line_denylist_kinds.update(
                kind for kind in kinds if kind.startswith("denylist_literal_")
            )
            findings.extend(Finding(kind, line_number) for kind in kinds)
        findings.extend(
            Finding(kind, 0)
            for kind in _full_text_denylist_kinds(text, denylist)
            if kind not in line_denylist_kinds
        )
    _verify_directory_unchanged(verified_root, initial_root)
    return sorted(findings, key=lambda item: (item.path, item.line, item.kind))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".", type=Path)
    parser.add_argument("--denylist-file", type=Path)
    parser.add_argument("--require-denylist", action="store_true")
    return parser


def _error_report() -> dict[str, object]:
    return {
        "error_code": "privacy_scan_failed",
        "matched_values_redacted": True,
        "status": "error",
    }


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        findings = scan(
            args.root,
            denylist_file=args.denylist_file,
            require_denylist=args.require_denylist,
        )
    except Exception:
        print(json.dumps(_error_report(), indent=2, sort_keys=True))
        return 2

    report = {
        "denylist_enforcement": (
            "required" if args.require_denylist else "optional_not_enforced"
        ),
        "denylist_provided": args.denylist_file is not None,
        "finding_count": len(findings),
        "findings": [
            {"kind": item.kind, "line": item.line, "path": item.path}
            for item in findings
        ],
        "matched_values_redacted": True,
        "scan_scope": (
            "bounded UTF-8 regular files and relative paths; "
            "unscanned or unstable filesystem entries fail"
        ),
        "status": "findings" if findings else "clean",
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main())
