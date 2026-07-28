from __future__ import annotations

import io
import tarfile
import zipfile
from pathlib import Path

import pytest

from scripts.verify_distribution_boundary import verify


def _write_wheel(path: Path, *, extra: tuple[str, bytes] | None = None) -> None:
    members = {
        "effect_witness/__init__.py": b"",
        "effect_witness-0.2.0.dist-info/licenses/LICENSE": b"license",
        "effect_witness-0.2.0.dist-info/licenses/THIRD_PARTY_NOTICES.md": b"notice",
    }
    if extra is not None:
        members[extra[0]] = extra[1]
    with zipfile.ZipFile(path, mode="w") as archive:
        for name, contents in members.items():
            archive.writestr(name, contents)


def _write_sdist(
    path: Path,
    *,
    extra: tuple[tarfile.TarInfo, bytes] | None = None,
) -> None:
    members = {
        "effect_witness-0.2.0/LICENSE": b"license",
        "effect_witness-0.2.0/THIRD_PARTY_NOTICES.md": b"notice",
        "effect_witness-0.2.0/src/effect_witness/__init__.py": b"",
    }
    repository = Path(__file__).resolve().parents[1]
    integration = repository / "integrations" / "filesystem"
    for filename in ("package.json", "package-lock.json", "lock-provenance.json"):
        members[f"effect_witness-0.2.0/integrations/filesystem/{filename}"] = (
            integration / filename
        ).read_bytes()
    members["effect_witness-0.2.0/integrations/langgraph/constraints.txt"] = (
        repository / "integrations" / "langgraph" / "constraints.txt"
    ).read_bytes()
    mini_swe_integration = repository / "integrations" / "mini-swe-agent"
    for filename in ("constraints-py312.txt", "wheel-provenance.json"):
        members[f"effect_witness-0.2.0/integrations/mini-swe-agent/{filename}"] = (
            mini_swe_integration / filename
        ).read_bytes()
    with tarfile.open(path, mode="w:gz") as archive:
        for name, contents in members.items():
            info = tarfile.TarInfo(name)
            info.size = len(contents)
            archive.addfile(info, io.BytesIO(contents))
        if extra is not None:
            info, contents = extra
            info.size = len(contents)
            archive.addfile(info, io.BytesIO(contents))


def _valid_dist(tmp_path: Path) -> Path:
    _write_wheel(tmp_path / "effect_witness-0.2.0-py3-none-any.whl")
    _write_sdist(tmp_path / "effect_witness-0.2.0.tar.gz")
    return tmp_path


def test_distribution_boundary_accepts_minimal_valid_pair(tmp_path: Path) -> None:
    report = verify(_valid_dist(tmp_path))

    assert report["project_legal_files_present"] is True
    assert report["integration_metadata_present"] is True
    assert report["npm_or_node_payloads_bundled"] is False


@pytest.mark.parametrize(
    "unsafe_name",
    (
        "effect_witness-0.2.0/./payload.txt",
        "effect_witness-0.2.0//payload.txt",
        "effect_witness-0.2.0/../payload.txt",
        "effect_witness-0.2.0/C" + ":/payload.txt",
    ),
)
def test_distribution_boundary_rejects_unsafe_paths(
    tmp_path: Path, unsafe_name: str
) -> None:
    wheel = tmp_path / "effect_witness-0.2.0-py3-none-any.whl"
    _write_wheel(wheel, extra=(unsafe_name, b"payload"))
    _write_sdist(tmp_path / "effect_witness-0.2.0.tar.gz")

    with pytest.raises(ValueError, match="unsafe member path"):
        verify(tmp_path)


def test_distribution_boundary_rejects_wheel_symlink(tmp_path: Path) -> None:
    wheel = tmp_path / "effect_witness-0.2.0-py3-none-any.whl"
    _write_wheel(wheel)
    with zipfile.ZipFile(wheel, mode="a") as archive:
        info = zipfile.ZipInfo("effect_witness/link")
        info.create_system = 3
        info.external_attr = 0o120777 << 16
        archive.writestr(info, b"target")
    _write_sdist(tmp_path / "effect_witness-0.2.0.tar.gz")

    with pytest.raises(ValueError, match="non-regular member"):
        verify(tmp_path)


def test_distribution_boundary_rejects_duplicate_wheel_member(tmp_path: Path) -> None:
    wheel = tmp_path / "effect_witness-0.2.0-py3-none-any.whl"
    _write_wheel(wheel)
    with zipfile.ZipFile(wheel, mode="a") as archive:
        archive.writestr("effect_witness/__init__.py", b"replacement")
    _write_sdist(tmp_path / "effect_witness-0.2.0.tar.gz")

    with pytest.raises(ValueError, match="duplicate member names"):
        verify(tmp_path)


@pytest.mark.parametrize("link_type", (tarfile.SYMTYPE, tarfile.LNKTYPE))
def test_distribution_boundary_rejects_sdist_links(
    tmp_path: Path, link_type: bytes
) -> None:
    _write_wheel(tmp_path / "effect_witness-0.2.0-py3-none-any.whl")
    link = tarfile.TarInfo("effect_witness-0.2.0/link")
    link.type = link_type
    link.linkname = "LICENSE"
    _write_sdist(
        tmp_path / "effect_witness-0.2.0.tar.gz",
        extra=(link, b""),
    )

    with pytest.raises(ValueError, match="non-regular member"):
        verify(tmp_path)


def test_distribution_boundary_rejects_duplicate_sdist_member(tmp_path: Path) -> None:
    _write_wheel(tmp_path / "effect_witness-0.2.0-py3-none-any.whl")
    duplicate = tarfile.TarInfo("effect_witness-0.2.0/LICENSE")
    _write_sdist(
        tmp_path / "effect_witness-0.2.0.tar.gz",
        extra=(duplicate, b"replacement"),
    )

    with pytest.raises(ValueError, match="duplicate member names"):
        verify(tmp_path)


def test_distribution_boundary_rejects_node_modules(tmp_path: Path) -> None:
    wheel = tmp_path / "effect_witness-0.2.0-py3-none-any.whl"
    _write_wheel(wheel, extra=("node_modules/runtime/index.js", b"payload"))
    _write_sdist(tmp_path / "effect_witness-0.2.0.tar.gz")

    with pytest.raises(ValueError, match="forbidden npm/runtime payload"):
        verify(tmp_path)


def test_distribution_boundary_rejects_bundled_upstream_wheel(
    tmp_path: Path,
) -> None:
    wheel = tmp_path / "effect_witness-0.2.0-py3-none-any.whl"
    _write_wheel(
        wheel,
        extra=("vendor/mini_swe_agent-2.4.6-py3-none-any.whl", b"payload"),
    )
    _write_sdist(tmp_path / "effect_witness-0.2.0.tar.gz")

    with pytest.raises(ValueError, match="forbidden runtime archive"):
        verify(tmp_path)


def test_distribution_boundary_requires_notice_in_wheel(tmp_path: Path) -> None:
    wheel = tmp_path / "effect_witness-0.2.0-py3-none-any.whl"
    with zipfile.ZipFile(wheel, mode="w") as archive:
        archive.writestr("effect_witness/__init__.py", b"")
        archive.writestr("effect_witness-0.2.0.dist-info/licenses/LICENSE", b"license")
    _write_sdist(tmp_path / "effect_witness-0.2.0.tar.gz")

    with pytest.raises(ValueError, match="THIRD_PARTY_NOTICES"):
        verify(tmp_path)
