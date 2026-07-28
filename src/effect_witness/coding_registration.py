"""Frozen registration for the schema-v5 mini-swe-agent evidence lane."""

from __future__ import annotations

import hashlib
from typing import Any, Final

from .coding_dependencies import (
    MINI_SWE_AGENT_DEVELOPMENT_STATUS as MINI_SWE_AGENT_DEVELOPMENT_STATUS,
)
from .coding_dependencies import (
    MINI_SWE_AGENT_LICENSE as MINI_SWE_AGENT_LICENSE,
)
from .coding_dependencies import (
    MINI_SWE_AGENT_PYTHON_REQUIRES as MINI_SWE_AGENT_PYTHON_REQUIRES,
)
from .coding_dependencies import (
    MINI_SWE_AGENT_VERSION as MINI_SWE_AGENT_VERSION,
)
from .coding_dependencies import (
    MINI_SWE_AGENT_WHEEL_BYTES as MINI_SWE_AGENT_WHEEL_BYTES,
)
from .coding_dependencies import (
    MINI_SWE_AGENT_WHEEL_FILENAME,
)
from .coding_dependencies import (
    MINI_SWE_AGENT_WHEEL_SHA256 as MINI_SWE_AGENT_WHEEL_SHA256,
)
from .coding_dependencies import (
    MINI_SWE_AGENT_WHEEL_URL as MINI_SWE_AGENT_WHEEL_URL,
)
from .models import sha256_json

SCHEMA_VERSION: Final = 5
LANE: Final = "mini_swe_agent_coding_reconciliation"
REGISTERED_ROUNDS: Final = 3
MACHINE_ARCHITECTURE: Final = "x86_64"

MINI_SWE_AGENT_WHEEL: Final = MINI_SWE_AGENT_WHEEL_FILENAME
MINI_SWE_AGENT_TRAJECTORY_FORMAT: Final = "mini-swe-agent-1.1"
PYTHON_CONSTRAINTS_SHA256: Final = (
    "a2a4b3cf0af75c357e1e4578d0cc4b0ffa222dcb9358a0b60a4e3a47512196eb"
)
PYTHON_CONSTRAINT_PACKAGE_COUNT: Final = 93

MINI_SWE_AGENT_RUNTIME_FILES: Final[dict[str, dict[str, Any]]] = {
    "minisweagent/__init__.py": {
        "bytes": 2371,
        "sha256": "0a708308b1b62cc020b60799c3d54f665845f795b3f0c4fdac787c96a38d12c7",
    },
    "minisweagent/agents/default.py": {
        "bytes": 8043,
        "sha256": "e8ef8aa365942d739c2ec5cb0879f60f377d2dc2de8ec670aaedf3bafb45a4c2",
    },
    "minisweagent/environments/local.py": {
        "bytes": 3617,
        "sha256": "01dd33ae6be897458611911cc0eee1389092ea9fc6788c7eb24773e7c6342b1c",
    },
    "minisweagent/exceptions.py": {
        "bytes": 729,
        "sha256": "0590393c56bee873c79a691dcb4f15cb39c85f1658598b84bfb295bfde56921d",
    },
    "minisweagent/models/__init__.py": {
        "bytes": 4466,
        "sha256": "eb141eae346d51af407b4faf868ad7e869fa4fff275415381fa8ef845616f351",
    },
    "minisweagent/models/test_models.py": {
        "bytes": 10728,
        "sha256": "44330685739f47e554b90fa73ccf019bc2e2b80e4c287c025f63ea4f5263b23e",
    },
    "minisweagent/models/utils/actions_text.py": {
        "bytes": 2629,
        "sha256": "e5997bba3ae3d541ff418317cc8dd9e9e17657de806679ef38ab1ad74e294047",
    },
    "minisweagent/models/utils/actions_toolcall.py": {
        "bytes": 4134,
        "sha256": "47b666412e4f838508b50009cf34c7f63fe15e9e40affc257a17c0829896526f",
    },
    "minisweagent/models/utils/actions_toolcall_response.py": {
        "bytes": 5568,
        "sha256": "36244c4383dde6059742eb1f99fe96b2a91f214f558ece463f81baef96018bcf",
    },
    "minisweagent/models/utils/openai_multimodal.py": {
        "bytes": 1865,
        "sha256": "c498ec2e97c0bf45c212a10de9f5d1b2d24d4de46a05fd0eaea975c1abe3f81f",
    },
    "minisweagent/utils/log.py": {
        "bytes": 996,
        "sha256": "aee0cc34a32b542f4d3ef09e1f03b7418cf98ec54d506401d9d4401003c05a9f",
    },
    "minisweagent/utils/serialize.py": {
        "bytes": 938,
        "sha256": "3035b27cfeffdf91117c72bc8131340bd9c5f67a3010baeb4ecd6b0c7406f462",
    },
}

OPERATION_ID: Final = "registered-calculator-fix-v1"
MUTATION_COMMAND: Final = (
    "git apply --check fix.patch && git apply fix.patch "
    "&& python -m unittest discover -s tests -q"
)
SUBMIT_COMMAND: Final = (
    "python -c \"print('COMPLETE_TASK_AND_SUBMIT_FINAL_OUTPUT'); "
    "print('registered synthetic fixture complete')\""
)
MUTATION_ACTION_SHA256: Final = hashlib.sha256(
    MUTATION_COMMAND.encode("utf-8")
).hexdigest()

INJECTED_TRAJECTORY_BYTES: Final = b'{"trajectory_format":'
INJECTED_TRAJECTORY_SHA256: Final = hashlib.sha256(
    INJECTED_TRAJECTORY_BYTES
).hexdigest()
INJECTED_TRAJECTORY_EXIT_CODE: Final = 17
UNRESOLVED_EXIT_CODE: Final = 23

SCENARIOS: Final[dict[str, dict[str, Any]]] = {
    "clean": {
        "fault": False,
        "policy": "blind",
        "restart": False,
        "tamper": False,
    },
    "save_fault_blind_restart": {
        "fault": True,
        "policy": "blind",
        "restart": True,
        "tamper": False,
    },
    "save_fault_reconcile": {
        "fault": True,
        "policy": "reconcile",
        "restart": True,
        "tamper": False,
    },
    "save_fault_reconcile_tampered": {
        "fault": True,
        "policy": "reconcile",
        "restart": True,
        "tamper": True,
    },
}
SCENARIO_ORDER: Final[tuple[str, ...]] = tuple(SCENARIOS)

REGISTERED_FIXTURE_PATHS: Final[tuple[str, ...]] = (
    ".gitattributes",
    ".gitignore",
    "fix.patch",
    "src/__init__.py",
    "src/calculator.py",
    "tests/__init__.py",
    "tests/test_calculator.py",
)


def _entry(path: str, size: int, sha256: str) -> dict[str, Any]:
    return {"bytes": size, "kind": "file", "path": path, "sha256": sha256}


def _tree(entries: list[dict[str, Any]]) -> dict[str, Any]:
    return {"entries": entries, "tree_sha256": sha256_json(entries)}


_COMMON_ENTRIES: Final = [
    _entry(
        ".gitattributes",
        14,
        "a79691a93b46e49ce460c26ef22afcc03d6eca1e63bf2edbc20e96159510f6c9",
    ),
    _entry(
        ".gitignore",
        23,
        "6feaded4e28ea86e001a6751b4e3d960e8b7c31b9616ff9936b79297086e809b",
    ),
    _entry(
        "fix.patch",
        250,
        "468b87f7f061fa7e25b232e9b6cdd67f08e45fd431d1e667e58453494ff10655",
    ),
    _entry("src/__init__.py", 0, hashlib.sha256(b"").hexdigest()),
    _entry("tests/__init__.py", 0, hashlib.sha256(b"").hexdigest()),
    _entry(
        "tests/test_calculator.py",
        226,
        "706f2f89a4dc9238a506e1ba71229c4d7424e3c0b7e9c6b20ea6bc30108c7737",
    ),
]

REGISTERED_TREES: Final[dict[str, dict[str, Any]]] = {
    "PRE": _tree(
        sorted(
            [
                *_COMMON_ENTRIES,
                _entry(
                    "src/calculator.py",
                    106,
                    "1aca482fa81bdc80fcd7924ecf2c5080f95732b73b23159deb49b44c314d4e68",
                ),
            ],
            key=lambda item: item["path"],
        )
    ),
    "POST": _tree(
        sorted(
            [
                *_COMMON_ENTRIES,
                _entry(
                    "src/calculator.py",
                    106,
                    "763e944ff51025080c40f2fb5791c2ef1af235eed522e18310588d9d0057b9da",
                ),
            ],
            key=lambda item: item["path"],
        )
    ),
    "TAMPERED": _tree(
        sorted(
            [
                *_COMMON_ENTRIES,
                _entry(
                    "src/calculator.py",
                    106,
                    "17880e64facfc933294487958371e202017ec7c386d5f24b2a413c32b5ee65e8",
                ),
            ],
            key=lambda item: item["path"],
        )
    ),
}

EVIDENCE_BOUNDARY: Final[dict[str, bool]] = {
    "absolute_paths_included": False,
    "commands_included": False,
    "environment_included": False,
    "fixture_content_included": False,
    "git_directory_included": False,
    "hostnames_included": False,
    "journal_database_included": False,
    "model_messages_included": False,
    "pids_included": False,
    "raw_agent_output_included": False,
    "raw_exception_messages_included": False,
    "raw_shell_output_included": False,
    "raw_trajectories_included": False,
    "timestamps_included": False,
    "upstream_wheel_included": False,
}

BLOCKED_CLAIMS: Final[tuple[str, ...]] = (
    "mini-swe-agent native resume or crash recovery",
    "exactly-once execution for arbitrary commands",
    "arbitrary coding-agent correctness or model repair ability",
    "SWE-bench, ProgramBench, repository, or industry performance",
    "safe sandboxing or general process-tree cleanup",
    "operating-system, power-loss, SQLite, or filesystem crash consistency",
    "production reliability, security, availability, or distributed consistency",
    "Windows and Linux equivalence beyond registered observations",
    "source authenticity without an external trusted Git or release digest",
    "upstream adoption, endorsement, independent review, or external users",
    "recruiting or headhunter outcomes",
)

EVIDENCE_SCOPE: Final = (
    "mini-swe-agent 2.4.6 DefaultAgent, DeterministicModel, and "
    "LocalEnvironment on one registered synthetic Git patch under one "
    "application-level trajectory-write fault"
)
