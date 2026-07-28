"""Exact registration for the v0.2 official-filesystem evidence lane."""

from __future__ import annotations

from typing import Any, Final

FILESYSTEM_PACKAGE: Final[dict[str, Any]] = {
    "name": "@modelcontextprotocol/server-filesystem",
    "version": "2026.7.10",
    "npm_metadata_git_head": "9a96ea6e5913736f92b88345bf51caeaaa8e719f",
    "npm_tarball_url": (
        "https://registry.npmjs.org/@modelcontextprotocol/"
        "server-filesystem/-/server-filesystem-2026.7.10.tgz"
    ),
    "npm_tarball_bytes": 17835,
    "npm_tarball_sha256": (
        "c17c1da371c8089cff2206cce3001194d8276bae2b5ac1e2b425b6612068e3ba"
    ),
    "npm_sha1": "b19597401bfbf055662eb9bc9bd92f13ecaf5661",
    "npm_sri": (
        "sha512-Mmjg4anFBD5OzbPnGJOA0jPPN8645ERhQk38HQLpSenx1ox9bfdPkm"
        "AzUnNjeQtqQGFLtKe13J20RtLBmUKMZA=="
    ),
    "npm_unpacked_bytes": 69088,
    "npm_file_count": 7,
    "npm_license_field": "SEE LICENSE IN LICENSE",
    "npm_tarball_license_file_present": False,
}

JAVASCRIPT_SDK: Final[dict[str, str]] = {
    "name": "@modelcontextprotocol/sdk",
    "version": "1.29.0",
    "license_field": "MIT",
    "npm_sri": (
        "sha512-zo37mZA9hJWpULgkRpowewez1y6ML5GsXJPY8FI0tBBCd77HEvza4jDq"
        "RKOXgHNn867PVGCyTdzqpz0izu5ZjQ=="
    ),
}

UPSTREAM_ROOT_LICENSE: Final[dict[str, Any]] = {
    "url": (
        "https://github.com/modelcontextprotocol/servers/blob/"
        "9a96ea6e5913736f92b88345bf51caeaaa8e719f/LICENSE"
    ),
    "bytes": 12227,
    "sha256": "0382b0057770ca05e9c350a50aa3b1c1fea84da0bc81d723bf00b9aa841be58a",
    "bounded_summary": (
        "the exact upstream root license describes an MIT-to-Apache-2.0 "
        "transition, retains MIT for contributions without relicensing consent, "
        "and assigns CC-BY-4.0 to non-specification documentation"
    ),
}

PACKAGE_JSON_SHA256: Final = (
    "7f16799cd666ac86cfddbfea46b0aea876d8b31a8c2e5bfd2824327da45c5e41"
)
PACKAGE_LOCK_SHA256: Final = (
    "dfc7fdc6962bae7ca42d7be7896c8ea3b3de847b3fc3930b8aa074bf0b887e6c"
)
LOCK_PROVENANCE_SHA256: Final = (
    "59bc7c5b569abad478f94f157aa6ee1d0e84d99a905dfd796a9f1f1c8528f7d5"
)
NODE_VERSION: Final = "v24.18.0"
NPM_VERSION: Final = "11.16.0"
PYTHON_MCP_VERSION: Final = "1.28.1"
EFFECT_WITNESS_PRODUCER_VERSIONS: Final[tuple[str, ...]] = (
    "0.2.0",
    "0.2.1",
    "0.3.0",
    "0.3.1",
    "0.3.2",
    "0.3.3",
    "0.4.0",
)
PROTOCOL_VERSION: Final = "2025-11-25"
SERVER_IDENTITY: Final[dict[str, str]] = {
    "name": "secure-filesystem-server",
    "version": "0.2.0",
}

SERVER_DISTRIBUTION_FILES: Final[dict[str, tuple[int, str]]] = {
    "README.md": (
        15068,
        "df276d57efc04b85fa1e8163fe1aa3d5b11d5b2a7de5ec51ba083e5cb04019cd",
    ),
    "dist/index.js": (
        28217,
        "ac12c0307497ebd1c8e0b0fe4b057165cded007cd7c7afc9aeaa68fefe68eb15",
    ),
    "dist/lib.js": (
        14315,
        "e2f5648317613530f60b582b8b0ed10c1beddc10c2d0926213300d827f27208e",
    ),
    "dist/path-utils.js": (
        4655,
        "2129214ece0aa7ee51a0e7d615bfdd9266c7284d8d5ecf02aff07d0a2c3dacd1",
    ),
    "dist/path-validation.js": (
        2904,
        "c2d5481e236814c3a4f32c74580f03fb19b25ff7d0b743cf9d51555c9399d9b6",
    ),
    "dist/roots-utils.js": (
        2760,
        "4074f48adb2a22d9d07792cbe0d8b8f59c63e499ef7b9722066fbb8d3d4d74b0",
    ),
    "package.json": (
        1169,
        "6b2c11d4d348cace9c652636d602713c377ba59d868e013de69f3a9046d61244",
    ),
}

EVIDENCE_BOUNDARY: Final[dict[str, bool]] = {
    "absolute_paths_included": False,
    "environment_included": False,
    "generated_fixture_content_included": False,
    "hostnames_included": False,
    "ports_included": False,
    "raw_mutating_tool_responses_included": False,
    "raw_server_logs_included": False,
    "raw_tool_result_text_included": False,
}

BLOCKED_CLAIMS: Final[tuple[str, ...]] = (
    "official MCP certification or conformance",
    "arbitrary MCP server correctness",
    "package-wide correctness",
    "production filesystem behavior",
    "permissions, timestamps, or symlink behavior",
    "concurrent mutation behavior",
    "security or vulnerability status",
    "external adoption or review",
)

TOOL_REGISTRATION: Final[dict[str, dict[str, Any]]] = {
    "create_directory": {
        "annotations": {
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
            "readOnlyHint": False,
        },
        "description_claims": {
            "multiple_nested_directories_in_one_operation": True,
        },
        "description_sha256": (
            "7e243b9bddbea4a901f0807ae14535972587b896eecde076b03dd4fbd3a9b5bd"
        ),
        "descriptor_without_description_sha256": (
            "c94b499eddf4edaede0012b988677f08ae0d656e89f55c5fdc0d23fc8213653f"
        ),
    },
    "edit_file": {
        "annotations": {
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": False,
            "readOnlyHint": False,
        },
        "description_claims": {
            "multiple_nested_directories_in_one_operation": False,
        },
        "description_sha256": (
            "1349a91ad62c6a43363a6af7995e3f29f44bf5e9c5310dadd8c278aec75e3969"
        ),
        "descriptor_without_description_sha256": (
            "c8b18d5ca7bc42fb1af3d7f2cf7672a7795b606c8ebbc8de650c5daf7a10b266"
        ),
    },
    "read_text_file": {
        "annotations": {
            "openWorldHint": False,
            "readOnlyHint": True,
        },
        "description_claims": {
            "multiple_nested_directories_in_one_operation": False,
        },
        "description_sha256": (
            "43033fa70cb5bafe3ded0443fe51f1edd90b4e9d45efac6118e4395d2524011f"
        ),
        "descriptor_without_description_sha256": (
            "198a479dd6085e2010bd7f02fa4b2ac613203d89df7cdf8a0a3f14cb3ea53a7a"
        ),
    },
    "write_file": {
        "annotations": {
            "destructiveHint": True,
            "idempotentHint": True,
            "openWorldHint": False,
            "readOnlyHint": False,
        },
        "description_claims": {
            "multiple_nested_directories_in_one_operation": False,
        },
        "description_sha256": (
            "182c8895da7eacc6f301ba5895d779aca5c0a29cf622fa14f34f728657f79688"
        ),
        "descriptor_without_description_sha256": (
            "c94a7bfdcd4fc68f2c9003afb775c44b4b7b7af5a007fa56a816ba1e8fc3401b"
        ),
    },
}

SCENARIO_ORDER: Final[tuple[str, ...]] = (
    "read_text_file",
    "create_directory",
    "create_directory_nested_claim",
    "write_file",
    "edit_file",
)
