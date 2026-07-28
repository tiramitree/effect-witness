from __future__ import annotations

from pathlib import Path

from effect_witness.coding_journal import (
    append_attempt,
    has_one_registered_commit,
    initialize_journal,
)
from effect_witness.coding_registration import REGISTERED_TREES


def _append_initial_commit(path: Path, *, before_tree_sha256: str) -> None:
    append_attempt(
        path,
        phase="initial",
        decision="EXECUTED",
        command_executed=True,
        returncode=0,
        before_tree_sha256=before_tree_sha256,
        after_tree_sha256=REGISTERED_TREES["POST"]["tree_sha256"],
    )


def test_registered_commit_requires_exact_pre_and_post_trees(
    tmp_path: Path,
) -> None:
    journal = tmp_path / "witness.sqlite"
    initialize_journal(journal)
    _append_initial_commit(
        journal,
        before_tree_sha256=REGISTERED_TREES["TAMPERED"]["tree_sha256"],
    )

    assert not has_one_registered_commit(
        journal,
        pre_tree_sha256=REGISTERED_TREES["PRE"]["tree_sha256"],
        post_tree_sha256=REGISTERED_TREES["POST"]["tree_sha256"],
    )


def test_registered_commit_accepts_one_exact_success(tmp_path: Path) -> None:
    journal = tmp_path / "witness.sqlite"
    initialize_journal(journal)
    _append_initial_commit(
        journal,
        before_tree_sha256=REGISTERED_TREES["PRE"]["tree_sha256"],
    )

    assert has_one_registered_commit(
        journal,
        pre_tree_sha256=REGISTERED_TREES["PRE"]["tree_sha256"],
        post_tree_sha256=REGISTERED_TREES["POST"]["tree_sha256"],
    )
