# Contributing

Small, evidence-backed changes are welcome through GitHub Issues and pull
requests.

Before proposing a change:

1. keep the fixture loopback-only and synthetic;
2. add a failing regression for behavior changes;
3. run `python -m pytest`, `python -m ruff check --no-cache src tests scripts`,
   `python -m ruff format --check --no-cache src tests scripts`, and
   `python scripts/privacy_scan.py .`;
4. update the claim boundary when evidence scope changes;
5. do not include personal data, private infrastructure details, credentials,
   copied proprietary code, or unverifiable performance claims.

For packaging or real-filesystem changes, also run:

```text
python -m build
python scripts/verify_distribution_boundary.py dist
python scripts/prepare_filesystem_server.py --output-dir <fresh-temp-dir>
effect-witness run-filesystem --output-dir <fresh-artifact-dir> --dependency-dir <fresh-temp-dir>
effect-witness verify-filesystem --artifact-dir <fresh-artifact-dir>
python scripts/privacy_scan.py <fresh-artifact-dir>
```

Keep the npm dependency tree outside the repository. Do not commit or package
`node_modules`, npm tarballs, Node runtimes, generated server logs, or
schema-v3 artifacts. Changes to the tracked npm package/lock pair must update
the exact dependency registration, installed-file allowlist, tests,
third-party notices, and claim boundary together. Dependency preparation must
remain lockfile-only and lifecycle-script-free.

For schema-v4 replay changes, also run:

```text
python -m pip install --constraint integrations/langgraph/constraints.txt -e ".[dev,langgraph-replay]"
python scripts/prepare_filesystem_server.py --output-dir <fresh-dependency-dir>
effect-witness run-replay \
  --constraints-file integrations/langgraph/constraints.txt \
  --output-dir <fresh-artifact-dir> \
  --dependency-dir <fresh-dependency-dir> \
  --source-revision UNCOMMITTED
effect-witness verify-replay --artifact-dir <fresh-artifact-dir>
python scripts/privacy_scan.py <fresh-artifact-dir>
```

Do not commit checkpoint/journal databases, WAL/SHM files, work roots, raw
logs, runtimes, `node_modules`, or temporary replay artifacts. A constraint
change must update its registered hash/count, direct-package registration,
third-party notices, distribution boundary, verifier mutations, and
claim/schema documentation together.

For schema-v5 coding-agent changes, use CPython 3.12 and also run:

```text
python -m pip install --no-deps -e .
python scripts/prepare_coding_agent.py \
  --output-dir <fresh-dependency-dir>
python -m pip install \
  --only-binary=:all: \
  --constraint integrations/mini-swe-agent/constraints-py312.txt \
  -e ".[dev]" \
  litellm==1.91.1 \
  <fresh-dependency-dir>/mini_swe_agent-2.4.6-py3-none-any.whl
effect-witness run-coding-agent \
  --constraints-file integrations/mini-swe-agent/constraints-py312.txt \
  --dependency-dir <fresh-dependency-dir> \
  --output-dir <fresh-artifact-dir> \
  --source-revision UNCOMMITTED
effect-witness verify-coding-agent \
  --artifact-dir <fresh-artifact-dir>
python scripts/privacy_scan.py <fresh-artifact-dir>
```

The dependency, artifact, and optional work directories must be fresh,
mutually disjoint, and outside user data or existing repositories. Do not
commit the downloaded wheel, raw trajectory, synthetic work root, `.git`
directory, journal database or WAL/SHM files, command output, or temporary
schema-v5 artifact.

Changes to the mini-swe-agent version, wheel, selected runtime-file set,
deterministic model outputs, command allowlist, synthetic fixture, scenario
matrix, supported platform, or 93-version constraint snapshot require matching
registration, dependency-provenance, tests, distribution-boundary,
third-party-notice, security, claim, and schema-document updates. Preserve the
separation between declared action, observed return code, durable journal
decision, workspace byte tree, and validation result. A Git diff or passing
test must never be used alone to infer a persisted external effect.

No contributor license agreement is currently used. Contributions submitted
to this Apache-2.0 repository are handled under the terms in `LICENSE`.

Opening an issue or pull request does not imply review, acceptance, or a
service-level commitment.
