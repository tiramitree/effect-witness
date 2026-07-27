"""Check that Python distributions do not bundle npm/runtime payloads."""

from __future__ import annotations

import argparse
import hashlib
import stat
import tarfile
import zipfile
from pathlib import Path, PurePosixPath

from effect_witness.filesystem_registration import (
    LOCK_PROVENANCE_SHA256,
    PACKAGE_JSON_SHA256,
    PACKAGE_LOCK_SHA256,
)
from effect_witness.langgraph_registration import PYTHON_CONSTRAINTS_SHA256
from effect_witness.models import canonical_json

_FORBIDDEN_PARTS = {
    "@modelcontextprotocol",
    "node_modules",
    "node_runtime",
}
_FORBIDDEN_SUFFIXES = {
    ".dll",
    ".dylib",
    ".exe",
    ".node",
    ".so",
    ".tar",
    ".tar.bz2",
    ".tar.gz",
    ".tar.xz",
    ".tgz",
    ".zip",
    "/node.exe",
    "/npm",
    "/npm.cmd",
    "/npx",
    "/npx.cmd",
}


def _safe_member_path(name: str) -> PurePosixPath:
    if "\\" in name:
        raise ValueError("distribution contains an unsafe member path")
    segments = name.split("/")
    if (
        not name
        or name.startswith("/")
        or any(segment in {"", ".", ".."} for segment in segments)
        or any(":" in segment for segment in segments)
    ):
        raise ValueError("distribution contains an unsafe member path")
    path = PurePosixPath(name)
    if path.is_absolute():
        raise ValueError("distribution contains an unsafe member path")
    return path


def _safe_members(names: list[str]) -> None:
    if len(names) != len(set(names)):
        raise ValueError("distribution contains duplicate member names")
    for name in names:
        path = _safe_member_path(name)
        normalized = path.as_posix()
        if any(part in _FORBIDDEN_PARTS for part in path.parts):
            raise ValueError("distribution contains a forbidden npm/runtime payload")
        lowered = f"/{normalized.casefold()}"
        if any(lowered.endswith(suffix) for suffix in _FORBIDDEN_SUFFIXES):
            raise ValueError("distribution contains a forbidden runtime archive")


def _require_project_legal_files(names: list[str], *, wheel: bool) -> None:
    paths = [_safe_member_path(name) for name in names]
    if wheel:
        license_matches = [
            path
            for path in paths
            if len(path.parts) >= 3
            and path.parts[-2:] == ("licenses", "LICENSE")
            and path.parts[-3].endswith(".dist-info")
        ]
        notice_matches = [
            path
            for path in paths
            if len(path.parts) >= 3
            and path.parts[-2:] == ("licenses", "THIRD_PARTY_NOTICES.md")
            and path.parts[-3].endswith(".dist-info")
        ]
    else:
        license_matches = [
            path for path in paths if len(path.parts) == 2 and path.name == "LICENSE"
        ]
        notice_matches = [
            path
            for path in paths
            if len(path.parts) == 2 and path.name == "THIRD_PARTY_NOTICES.md"
        ]
    if len(license_matches) != 1 or len(notice_matches) != 1:
        raise ValueError(
            "distribution must contain exactly one project LICENSE and "
            "THIRD_PARTY_NOTICES.md"
        )


def _verify_wheel_members(archive: zipfile.ZipFile) -> list[str]:
    infos = archive.infolist()
    names = [info.filename for info in infos]
    _safe_members(names)
    for info in infos:
        if info.is_dir():
            raise ValueError("wheel contains a directory member")
        unix_mode = info.external_attr >> 16
        file_type = stat.S_IFMT(unix_mode)
        if file_type not in {0, stat.S_IFREG}:
            raise ValueError("wheel contains a non-regular member")
    _require_project_legal_files(names, wheel=True)
    return names


def _verify_sdist_integration_metadata(
    archive: tarfile.TarFile,
    members: list[tarfile.TarInfo],
) -> None:
    expected = {
        ("filesystem", "package.json"): PACKAGE_JSON_SHA256,
        ("filesystem", "package-lock.json"): PACKAGE_LOCK_SHA256,
        ("filesystem", "lock-provenance.json"): LOCK_PROVENANCE_SHA256,
        ("langgraph", "constraints.txt"): PYTHON_CONSTRAINTS_SHA256,
    }
    for (integration, filename), expected_sha256 in expected.items():
        matches = [
            member
            for member in members
            if PurePosixPath(member.name).parts[-3:]
            == ("integrations", integration, filename)
        ]
        if len(matches) != 1 or not matches[0].isfile():
            raise ValueError(
                "source distribution is missing exact integration metadata"
            )
        extracted = archive.extractfile(matches[0])
        if extracted is None:
            raise ValueError("source distribution integration metadata is unreadable")
        content = extracted.read()
        if hashlib.sha256(content).hexdigest() != expected_sha256:
            raise ValueError("source distribution integration metadata differs")


def _verify_sdist_members(archive: tarfile.TarFile) -> list[str]:
    members = archive.getmembers()
    names = [member.name for member in members]
    _safe_members(names)
    for member in members:
        if member.issym() or member.islnk() or member.isdev() or not member.isfile():
            raise ValueError("source distribution contains a non-regular member")
    _require_project_legal_files(names, wheel=False)
    _verify_sdist_integration_metadata(archive, members)
    return names


def verify(dist_dir: Path) -> dict[str, object]:
    wheels = sorted(dist_dir.glob("*.whl"))
    sdists = sorted(dist_dir.glob("*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise ValueError("expected exactly one wheel and one source distribution")
    with zipfile.ZipFile(wheels[0]) as archive:
        wheel_members = _verify_wheel_members(archive)
        if any("integrations" in PurePosixPath(name).parts for name in wheel_members):
            raise ValueError("wheel unexpectedly contains integration metadata")
    with tarfile.open(sdists[0], mode="r:gz") as archive:
        sdist_members = _verify_sdist_members(archive)
    return {
        "integration_metadata_present": True,
        "project_legal_files_present": True,
        "npm_or_node_payloads_bundled": False,
        "sdist_members_checked": len(sdist_members),
        "wheel_members_checked": len(wheel_members),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("dist_dir", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = verify(args.dist_dir)
    except Exception as exc:
        print(
            canonical_json(
                {
                    "error_type": type(exc).__name__,
                    "verified": False,
                }
            )
        )
        return 1
    print(canonical_json({"verified": True, **report}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
