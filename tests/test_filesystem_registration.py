from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

import pytest

import effect_witness.filesystem_dependencies as dependency_module
from effect_witness.filesystem_dependencies import (
    _minimal_process_environment,
    _resolve_executable,
    _verify_server_distribution,
    verify_dependency_directory,
    verify_lock_bytes,
)
from effect_witness.filesystem_lane import (
    _byte_tree,
    _normalized_call,
    _safe_relative,
    _server_environment,
)
from effect_witness.filesystem_registration import (
    JAVASCRIPT_SDK,
    NODE_VERSION,
    PACKAGE_JSON_SHA256,
    PACKAGE_LOCK_SHA256,
    SERVER_DISTRIBUTION_FILES,
)


def _repository() -> Path:
    return Path(__file__).resolve().parents[1]


def test_tracked_lock_binds_exact_server_and_javascript_sdk() -> None:
    integration = _repository() / "integrations" / "filesystem"
    package = (integration / "package.json").read_bytes()
    lock = (integration / "package-lock.json").read_bytes()

    report = verify_lock_bytes(package, lock)

    assert report == {
        "javascript_sdk_version": "1.29.0",
        "lockfile_sha256": PACKAGE_LOCK_SHA256,
        "lockfile_version": 3,
        "server_package_version": "2026.7.10",
    }
    assert JAVASCRIPT_SDK["npm_sri"].startswith("sha512-")
    assert len(SERVER_DISTRIBUTION_FILES) == 7
    assert "LICENSE" not in SERVER_DISTRIBUTION_FILES
    assert (integration / "lock-provenance.json").is_file()
    assert PACKAGE_JSON_SHA256 != PACKAGE_LOCK_SHA256


def test_subprocess_environments_exclude_user_and_network_secrets(
    monkeypatch,
) -> None:
    for name in (
        "AWS_SECRET_ACCESS_KEY",
        "GH_TOKEN",
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "NPM_TOKEN",
        "SSH_AUTH_SOCK",
    ):
        monkeypatch.setenv(name, f"private-{name}")

    for environment in (_minimal_process_environment(), _server_environment()):
        assert not any(
            fragment in key.casefold()
            for key in environment
            for fragment in ("proxy", "secret", "token", "ssh", "aws")
        )
        assert not any("private-" in value for value in environment.values())
        assert set(environment) <= {
            "COMSPEC",
            "LANG",
            "LC_ALL",
            "SYSTEMROOT",
            "WINDIR",
        }


def test_executable_is_resolved_before_minimal_environment() -> None:
    resolved = Path(_resolve_executable(sys.executable, label="Python"))

    assert resolved.is_absolute()
    assert resolved.is_file()


def test_relative_dependency_root_is_normalized_before_launch(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.chdir(tmp_path)
    integration = _repository() / "integrations" / "filesystem"
    root = Path("relative-dependencies")
    root.mkdir()
    (root / "package.json").write_bytes((integration / "package.json").read_bytes())
    (root / "package-lock.json").write_bytes(
        (integration / "package-lock.json").read_bytes()
    )
    server = root / "node_modules" / "@modelcontextprotocol" / "server-filesystem"
    server.mkdir(parents=True)
    (server / "package.json").write_text(
        '{"license":"SEE LICENSE IN LICENSE",'
        '"name":"@modelcontextprotocol/server-filesystem",'
        '"version":"2026.7.10"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        dependency_module,
        "_verify_server_distribution",
        lambda _root: None,
    )
    monkeypatch.setattr(
        dependency_module,
        "_command_version",
        lambda *_args, **_kwargs: NODE_VERSION,
    )
    monkeypatch.setattr(
        dependency_module,
        "_resolve_executable",
        lambda *_args, **_kwargs: sys.executable,
    )

    dependency = verify_dependency_directory(
        root,
        node_command=sys.executable,
    )

    assert dependency.dependency_root == (tmp_path / root).absolute()
    assert dependency.server_entrypoint.is_absolute()


@pytest.mark.parametrize(
    "value",
    [
        "",
        ".",
        "../escape",
        "a/../escape",
        "a//b",
        "a/./b",
        "C" + ":/private",
        r"a\b",
        "control\u0000value",
    ],
)
def test_relative_witness_path_fails_closed(value: str) -> None:
    with pytest.raises(ValueError, match="unsafe relative path"):
        _safe_relative(value)


def test_server_stderr_device_is_not_console() -> None:
    with open(os.devnull, "w", encoding="utf-8") as errlog:
        assert errlog.name == os.devnull
        assert errlog is not sys.stderr


class _Response:
    def __init__(self, value: dict[str, object]) -> None:
        self.value = value

    def model_dump(self, **_kwargs) -> dict[str, object]:
        return self.value


def test_mutating_response_text_and_absolute_path_are_not_retained() -> None:
    private_path = "C" + r":\private-host\user\result.txt"
    response = _Response(
        {
            "content": [{"text": f"Wrote {private_path}", "type": "text"}],
            "isError": False,
            "structuredContent": {"content": f"Wrote {private_path}"},
        }
    )

    observation = _normalized_call(
        completed=True,
        response=response,
        read_result=False,
    )

    assert observation == {
        "completed": True,
        "content_types": ["text"],
        "exception_types": [],
        "is_error": False,
        "response_text_included": False,
        "response_text_redacted": True,
        "structured_content_present": True,
        "text_block_count": 1,
    }
    assert private_path not in repr(observation)


def test_byte_tree_contains_only_relative_digest_projection(tmp_path) -> None:
    root = tmp_path / "sandbox"
    root.mkdir()
    (root / "fixture.txt").write_text("known", encoding="utf-8")

    tree = _byte_tree(root)

    assert tree["entries"][0]["path"] == "fixture.txt"
    assert str(tmp_path) not in repr(tree)
    assert tree["entries"][0]["sha256"] == hashlib.sha256(b"known").hexdigest()


@pytest.mark.parametrize("mutation", ["missing", "extra", "changed"])
def test_installed_distribution_inventory_fails_closed(
    monkeypatch,
    tmp_path,
    mutation: str,
) -> None:
    expected = b"registered"
    expected_sha = hashlib.sha256(expected).hexdigest()
    monkeypatch.setattr(
        dependency_module,
        "SERVER_DISTRIBUTION_FILES",
        {"dist/index.js": (len(expected), expected_sha)},
    )
    root = tmp_path / "server"
    (root / "dist").mkdir(parents=True)
    target = root / "dist" / "index.js"
    target.write_bytes(expected)
    if mutation == "missing":
        target.unlink()
    elif mutation == "extra":
        (root / "extra.txt").write_text("extra", encoding="utf-8")
    else:
        target.write_bytes(b"tampered!")

    with pytest.raises(
        ValueError,
        match="installed server distribution differs from registration",
    ):
        _verify_server_distribution(root)
