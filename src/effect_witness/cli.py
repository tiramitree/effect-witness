"""Command-line entry point."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

from .artifact import verify_artifact
from .fixture_server import main as fixture_main
from .models import FaultMode, canonical_json
from .suite import run_suite


def _source_revision(value: str) -> str:
    if value == "UNCOMMITTED" or re.fullmatch(r"[0-9a-f]{40}", value):
        return value
    raise argparse.ArgumentTypeError(
        "source revision must be UNCOMMITTED or a 40-character lowercase Git commit"
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="effect-witness")
    subparsers = parser.add_subparsers(dest="command", required=True)
    fixture = subparsers.add_parser(
        "serve-fixture",
        help="run the deterministic local MCP fixture",
    )
    fixture.add_argument("--database", required=True)
    fixture.add_argument("--host", choices=["127.0.0.1"], default="127.0.0.1")
    fixture.add_argument("--port", required=True, type=int)
    fixture.add_argument("--response-delay-seconds", default=0.75, type=float)
    fixture.add_argument(
        "--fault-mode",
        choices=[item.value for item in FaultMode],
        default=FaultMode.CLEAN.value,
    )
    fixture.add_argument("--readiness-nonce", required=True)
    fixture.add_argument("--test-mode", action="store_true")
    run = subparsers.add_parser(
        "run",
        help="run the local MCP scenario suite and seal evidence",
    )
    run.add_argument("--output-dir", required=True, type=Path)
    run.add_argument("--work-dir", type=Path)
    run.add_argument(
        "--source-revision",
        default="UNCOMMITTED",
        type=_source_revision,
        help="source commit recorded in evidence, or UNCOMMITTED",
    )
    verify = subparsers.add_parser(
        "verify",
        help="verify artifact integrity and internal consistency offline",
    )
    verify.add_argument("--artifact-dir", required=True, type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "run":
        summary = run_suite(
            args.output_dir,
            work_dir=args.work_dir,
            source_revision=args.source_revision,
        )
        report = verify_artifact(args.output_dir)
        print(canonical_json({"summary": summary, "verification": report}))
        return 0 if summary["all_expectations_met"] and report["verified"] else 1
    if args.command == "verify":
        report = verify_artifact(args.artifact_dir)
        print(canonical_json(report))
        return 0 if report["verified"] else 1
    if args.command == "serve-fixture":
        forwarded = [
            "--database",
            args.database,
            "--host",
            args.host,
            "--port",
            str(args.port),
            "--response-delay-seconds",
            str(args.response_delay_seconds),
            "--fault-mode",
            args.fault_mode,
            "--readiness-nonce",
            args.readiness_nonce,
        ]
        if args.test_mode:
            forwarded.append("--test-mode")
        return fixture_main(forwarded)
    raise AssertionError("unreachable command")


if __name__ == "__main__":
    raise SystemExit(main())
