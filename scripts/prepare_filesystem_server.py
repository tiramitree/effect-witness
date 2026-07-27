"""Materialize the exact external npm dependency closure for the real lane."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path

from effect_witness.filesystem_dependencies import (
    _command_version,
    _resolve_executable,
    verify_dependency_directory,
    verify_lock_bytes,
)
from effect_witness.filesystem_paths import (
    create_staging_directory,
    publish_staging_directory,
    remove_owned_directory,
)
from effect_witness.filesystem_registration import NPM_VERSION
from effect_witness.models import canonical_json


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--npm-command", default="npm")
    parser.add_argument("--node-command", default="node")
    return parser


def _run_npm(
    command: list[str],
    *,
    cwd: Path,
    cache: Path,
    node_directory: Path,
) -> None:
    config = cwd / "_npm_config"
    home = cwd / "_npm_home"
    config.mkdir(exist_ok=True)
    home.mkdir(exist_ok=True)
    userconfig = config / "user.npmrc"
    globalconfig = config / "global.npmrc"
    userconfig.write_text("", encoding="utf-8", newline="\n")
    globalconfig.write_text("", encoding="utf-8", newline="\n")
    environment = {
        key: os.environ[key]
        for key in (
            "COMSPEC",
            "PATHEXT",
            "SYSTEMROOT",
            "TEMP",
            "TMP",
            "TMPDIR",
            "WINDIR",
        )
        if key in os.environ
    }
    environment.update(
        {
            "HOME": str(home),
            "PATH": str(node_directory),
            "npm_config_audit": "false",
            "npm_config_cache": str(cache),
            "npm_config_fund": "false",
            "npm_config_globalconfig": str(globalconfig),
            "npm_config_ignore_scripts": "true",
            "npm_config_registry": "https://registry.npmjs.org/",
            "npm_config_update_notifier": "false",
            "npm_config_userconfig": str(userconfig),
        }
    )
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            env=environment,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
            timeout=300,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise RuntimeError(f"npm invocation failed ({type(exc).__name__})") from None
    if completed.returncode != 0:
        raise RuntimeError("npm invocation returned a nonzero status")


def prepare(
    output_dir: Path,
    *,
    npm_command: str,
    node_command: str,
) -> dict[str, object]:
    output, staging = create_staging_directory(
        output_dir,
        label="dependency output directory",
    )
    published = False
    repository = Path(__file__).resolve().parents[1]
    integration = repository / "integrations" / "filesystem"
    registered_package = integration / "package.json"
    registered_lock = integration / "package-lock.json"
    destination_package = staging / "package.json"
    destination_lock = staging / "package-lock.json"
    try:
        verify_lock_bytes(
            registered_package.read_bytes(),
            registered_lock.read_bytes(),
        )
        shutil.copyfile(registered_package, destination_package)
        shutil.copyfile(registered_lock, destination_lock)
        cache = staging / "_npm_cache"
        resolved_node = _resolve_executable(node_command, label="Node")
        node_directory = Path(resolved_node).parent
        npm_version = _command_version(
            npm_command,
            "--version",
            label="npm",
            path_entries=(str(node_directory),),
        )
        if npm_version != NPM_VERSION:
            raise ValueError("npm version differs from registration")
        resolved_npm = _resolve_executable(npm_command, label="npm")
        generated_paths = (
            cache,
            staging / "_npm_config",
            staging / "_npm_home",
        )
        try:
            _run_npm(
                [
                    resolved_npm,
                    "ci",
                    "--ignore-scripts",
                    "--no-audit",
                    "--no-fund",
                ],
                cwd=staging,
                cache=cache,
                node_directory=node_directory,
            )
        finally:
            for generated in generated_paths:
                remove_owned_directory(
                    generated,
                    label="generated npm working directory",
                )
        verify_dependency_directory(
            staging,
            node_command=node_command,
        )
        publish_staging_directory(
            staging,
            output,
            label="dependency output directory",
        )
        published = True
        dependency = verify_dependency_directory(
            output,
            node_command=node_command,
        )
        return {
            "javascript_sdk_version": "1.29.0",
            "lockfile_sha256": dependency.lockfile_sha256,
            "node_version": dependency.node_version,
            "npm_version": npm_version,
            "server_package_version": "2026.7.10",
        }
    except Exception as original:
        try:
            remove_owned_directory(
                output if published else staging,
                label="dependency output directory",
            )
        except Exception as cleanup:
            raise RuntimeError(
                "dependency preparation and cleanup both failed "
                f"({type(original).__name__}, {type(cleanup).__name__})"
            ) from None
        raise


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        report = prepare(
            args.output_dir,
            npm_command=args.npm_command,
            node_command=args.node_command,
        )
    except Exception as exc:
        print(
            canonical_json(
                {
                    "error_type": type(exc).__name__,
                    "prepared": False,
                }
            )
        )
        return 1
    print(canonical_json({"prepared": True, **report}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
