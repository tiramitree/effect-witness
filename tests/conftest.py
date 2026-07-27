from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from effect_witness.suite import run_suite


@pytest.fixture(scope="session")
def schema_v2_artifact_template(
    tmp_path_factory: pytest.TempPathFactory,
) -> Path:
    root = tmp_path_factory.mktemp("schema-v2-artifact-template")
    artifact = root / "artifact"
    run_suite(artifact, work_dir=root / "work")
    return artifact


@pytest.fixture
def schema_v2_artifact(
    tmp_path: Path,
    schema_v2_artifact_template: Path,
) -> Path:
    artifact = tmp_path / "artifact"
    shutil.copytree(schema_v2_artifact_template, artifact)
    return artifact
