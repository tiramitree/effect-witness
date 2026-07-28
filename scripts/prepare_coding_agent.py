"""Download and atomically publish the exact registered mini-swe-agent wheel."""

from __future__ import annotations

import argparse
import hashlib
import urllib.error
import urllib.request
from pathlib import Path

from effect_witness.coding_dependencies import (
    MINI_SWE_AGENT_PACKAGE,
    MINI_SWE_AGENT_WHEEL_BYTES,
    MINI_SWE_AGENT_WHEEL_FILENAME,
    MINI_SWE_AGENT_WHEEL_SHA256,
    MINI_SWE_AGENT_WHEEL_URL,
    MiniSweWheel,
    verify_mini_swe_wheel,
    verify_wheel_provenance_bytes,
)
from effect_witness.filesystem_paths import (
    create_staging_directory,
    publish_staging_directory,
    remove_owned_directories,
)
from effect_witness.models import canonical_json

_DOWNLOAD_CHUNK_BYTES = 64 * 1024


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", required=True, type=Path)
    return parser


def _download_registered_wheel(destination: Path) -> None:
    request = urllib.request.Request(
        MINI_SWE_AGENT_WHEEL_URL,
        headers={"User-Agent": "effect-witness-dependency-preparer/0.4.0"},
        method="GET",
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    digest = hashlib.sha256()
    total = 0
    try:
        with (
            opener.open(request, timeout=60) as response,
            destination.open("xb") as output,
        ):
            while chunk := response.read(_DOWNLOAD_CHUNK_BYTES):
                total += len(chunk)
                if total > MINI_SWE_AGENT_WHEEL_BYTES:
                    raise ValueError("mini-swe-agent download exceeds registered size")
                digest.update(chunk)
                output.write(chunk)
    except (OSError, TimeoutError, urllib.error.URLError) as exc:
        raise RuntimeError(
            f"mini-swe-agent download failed ({type(exc).__name__})"
        ) from None
    if total != MINI_SWE_AGENT_WHEEL_BYTES:
        raise ValueError("mini-swe-agent download size differs from registration")
    if digest.hexdigest() != MINI_SWE_AGENT_WHEEL_SHA256:
        raise ValueError("mini-swe-agent download digest differs from registration")


def prepare_mini_swe_wheel(output_dir: str | Path) -> MiniSweWheel:
    """Prepare one verified wheel below a newly published owned directory."""

    output, staging = create_staging_directory(
        output_dir,
        label="mini-swe-agent dependency output directory",
    )
    published = False
    repository = Path(__file__).resolve().parents[1]
    provenance_path = (
        repository / "integrations" / "mini-swe-agent" / "wheel-provenance.json"
    )
    try:
        try:
            provenance = provenance_path.read_bytes()
        except OSError as exc:
            raise ValueError(
                f"mini-swe-agent provenance is unavailable ({type(exc).__name__})"
            ) from None
        verify_wheel_provenance_bytes(provenance)
        staged_wheel = staging / MINI_SWE_AGENT_WHEEL_FILENAME
        _download_registered_wheel(staged_wheel)
        verify_mini_swe_wheel(staged_wheel)
        publish_staging_directory(
            staging,
            output,
            label="mini-swe-agent dependency output directory",
        )
        published = True
        return verify_mini_swe_wheel(output / MINI_SWE_AGENT_WHEEL_FILENAME)
    except BaseException as original:
        try:
            remove_owned_directories(
                [
                    (
                        output if published else staging,
                        "mini-swe-agent dependency output directory",
                    )
                ]
            )
        except Exception as cleanup:
            raise RuntimeError(
                "mini-swe-agent preparation and cleanup both failed "
                f"({type(original).__name__}, {type(cleanup).__name__})"
            ) from None
        raise


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        wheel = prepare_mini_swe_wheel(args.output_dir)
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
    print(
        canonical_json(
            {
                "bytes": wheel.bytes,
                "filename": MINI_SWE_AGENT_WHEEL_FILENAME,
                "package": MINI_SWE_AGENT_PACKAGE,
                "prepared": True,
                "sha256": wheel.sha256,
                "version": wheel.version,
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
