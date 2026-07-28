"""Strict LocalEnvironment adapter for one registered coding effect."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .coding_fixture import snapshot
from .coding_journal import append_attempt, has_one_registered_commit
from .coding_registration import (
    MUTATION_COMMAND,
    REGISTERED_TREES,
    SUBMIT_COMMAND,
)
from .models import json_exact_equal


class UnresolvedEffectState(RuntimeError):
    """The durable journal and registered workspace postcondition disagree."""


class CodingEffectAdapter:
    """Whitelist two exact actions and reconcile only the registered mutation."""

    def __init__(
        self,
        base: Any,
        *,
        journal: Path,
        phase: str,
        policy: str,
        workspace: Path,
    ):
        if phase not in {"initial", "restart"}:
            raise ValueError("unregistered coding-agent phase")
        if policy not in {"blind", "reconcile"}:
            raise ValueError("unregistered coding-agent policy")
        self.base = base
        self.journal = journal
        self.phase = phase
        self.policy = policy
        self.workspace = workspace

    def execute(self, action: dict[str, Any], cwd: str = "") -> dict[str, Any]:
        if set(action) != {"command"}:
            raise ValueError("coding-agent action shape differs from registration")
        command = action["command"]
        if command == SUBMIT_COMMAND:
            return self.base.execute(action, cwd=cwd)
        if command != MUTATION_COMMAND:
            raise ValueError("coding-agent command differs from registration")

        before = snapshot(self.workspace)
        if self.policy == "reconcile" and self.phase == "restart":
            committed = has_one_registered_commit(
                self.journal,
                pre_tree_sha256=REGISTERED_TREES["PRE"]["tree_sha256"],
                post_tree_sha256=REGISTERED_TREES["POST"]["tree_sha256"],
            )
            if committed and json_exact_equal(before, REGISTERED_TREES["POST"]):
                append_attempt(
                    self.journal,
                    phase=self.phase,
                    decision="RECONCILED",
                    command_executed=False,
                    returncode=0,
                    before_tree_sha256=before["tree_sha256"],
                    after_tree_sha256=before["tree_sha256"],
                )
                return {
                    "exception_info": "",
                    "output": "registered postcondition confirmed",
                    "returncode": 0,
                }
            append_attempt(
                self.journal,
                phase=self.phase,
                decision="UNRESOLVED",
                command_executed=False,
                returncode=None,
                before_tree_sha256=before["tree_sha256"],
                after_tree_sha256=before["tree_sha256"],
            )
            raise UnresolvedEffectState("registered coding effect cannot be reconciled")

        result = self.base.execute(action, cwd=cwd)
        after = snapshot(self.workspace)
        returncode = result.get("returncode")
        if type(returncode) is not int:
            raise RuntimeError("LocalEnvironment returned an invalid return code")
        append_attempt(
            self.journal,
            phase=self.phase,
            decision="EXECUTED",
            command_executed=True,
            returncode=returncode,
            before_tree_sha256=before["tree_sha256"],
            after_tree_sha256=after["tree_sha256"],
        )
        return result

    def get_template_vars(self, **kwargs: Any) -> dict[str, Any]:
        return self.base.get_template_vars(**kwargs)

    def serialize(self) -> dict[str, Any]:
        return self.base.serialize()
