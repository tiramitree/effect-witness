# EffectWitness

EffectWitness is a pre-alpha, local-first evidence workbench with four
isolated lanes for declared tool effects, bounded real-implementation
observations, cross-process workflow replay, and deterministic coding-agent
reconciliation.

The first two lanes ask one narrow question:

> When an agent tool declares an effect-related hint, do a client's observations
> and the bundled fixture's durable synthetic effect facts match that declaration
> under repeated or threaded calls, response loss, process exit, and restart?

The third asks what a fixed LangGraph task, checkpoint, MCP call, and visible
byte tree show when a registered post-effect exception is followed by a second
worker process.

The fourth asks what mini-swe-agent 2.4.6 `DefaultAgent`,
`DeterministicModel`, and `LocalEnvironment` show when one registered synthetic
Git patch succeeds but the first trajectory write then fails at the
application level. It keeps the agent's declared action, command observation,
out-of-workspace durable journal, Git byte tree, and independent validation
results separate.

It deliberately separates three fact domains:

1. the metadata and input schema returned by the protocol;
2. what the client observed and decided;
3. what the controlled fixture durably recorded.

Schema v2 and schema v3 target MCP tool annotations. The
[official MCP explanation](https://blog.modelcontextprotocol.io/posts/2026-03-16-tool-annotations/)
describes these annotations as untrusted hints, so EffectWitness never treats a
mismatch as automatic protocol nonconformance. Its result vocabulary is
`MATCH`, `MISMATCH`, `UNRESOLVED`, and `NOT_APPLICABLE`.

## Status and evidence boundary

This repository is an early candidate under active pre-alpha development. It
has no verified external users, adoption, independent reproduction, third-party
review, production deployment, or recruiting outcome.

The schema-v2 lane is a controlled dual-view fixture, not a general black-box
observer for arbitrary third-party tools. It uses synthetic effects, loopback
MCP Streamable HTTP, separate client and server SQLite databases, and
deterministic test faults.

The separate schema-v3 lane executes one exact official filesystem-server npm
distribution over MCP stdio. It observes only a registered five-scenario,
twice-called slice through fail-closed relative byte trees. It does not extend
the result to the rest of the package or to production filesystem behavior.

The separate schema-v4 lane observes four exact LangGraph Functional API
failure/resume scenarios for ten rounds each. Fault and resume run in separate
Python processes against the same SQLite checkpoint and registered MCP
filesystem effect. It compares blind replay with one exact byte-tree
reconciliation policy; it is not a general durability or recovery benchmark.

The separate schema-v5 lane observes four exact mini-swe-agent coding
scenarios for three rounds each on CPython 3.12 x86-64 Windows or Linux. It
uses a deterministic in-process model and one synthetic Git patch, with no
model API or paid-service call. Its registered fault is a first trajectory
write failure after the mutation command and durable journal record, not a
mini-swe-agent native resume, process crash, power loss, or filesystem
crash-consistency experiment.

It does **not** establish exactly-once execution, official MCP certification,
distributed consistency, security, sandboxing, production reliability,
mini-swe-agent native resume, model capability or repair performance,
framework superiority, or external usefulness. See the full
[claim boundary](docs/claims.md).

## Implemented reproducible slices

The schema-v2 synthetic fixture includes:

- a separate MCP fixture process with per-launch nonce readiness;
- loopback-only transport with environment proxies disabled;
- protocol-visible arguments that exclude attempt and fault controls;
- server-generated attempt identities and one-shot launch fault plans;
- SQLite WAL/FULL client journal and server effect facts;
- clean repeats, pre-commit exit, post-commit response loss, post-commit exit,
  restart/reconciliation, barrier-synchronized eight-call concurrent repetition,
  and payload conflict;
- truthful and deliberately misleading annotation controls;
- canonical JSON, JUnit, SHA-256 manifest, and a schema-v2 offline verifier;
- a fail-closed privacy scanner for UTF-8 content, filenames, and relative paths;
- structured failures for unscanned files, with sensitive paths redacted;
- no model API or paid-service client.

The registered ten-scenario matrix expects:

| Result | Count | Meaning in this fixture |
|---|---:|---|
| `MATCH` | 3 | Truthful repeated idempotent controls |
| `MISMATCH` | 4 | Deliberately misleading idempotent/read-only controls |
| `NOT_APPLICABLE` | 3 | A single ambiguous call or confirmed pre-commit absence does not test repeat-effect safety |

An expected `MISMATCH` is a passing negative control. It is not a JUnit
failure.

The bundled [reference artifact](evidence/README.md) records this matrix and
binds it to the exact source revision used to build the 0.1.0 wheel.

The schema-v3 real-implementation lane includes:

- Python MCP SDK 1.28.1 over stdio to
  `@modelcontextprotocol/server-filesystem` version `2026.7.10`;
- Node 24.18.0, npm 11.16.0, and a tracked lockfile resolving the JavaScript
  MCP SDK to 1.29.0;
- exact installed-file size and SHA-256 registration for the seven files in
  that server distribution;
- `read_text_file`, simple and nested `create_directory`, `write_file`, and
  `edit_file`, each called twice;
- fail-closed S0/S1/S2 relative byte-tree observations;
- registered annotation, descriptor, stimulus, dependency, protocol, and
  server-identity hashes or facts;
- schema-v3 canonical JSON, JUnit, manifest, and a strict offline verifier
  separate from the schema-v2 verifier;
- no npm package, `node_modules`, server log, raw mutation response, absolute
  runtime path, fixture content, environment, hostname, or port in the
  artifact.

The Windows observation for the registered nested-create input is an MCP error
with no visible byte-tree change. The Linux gate accepts only that observation
or creation of the two registered nested directories. This is an
OS/input/version-bounded observation, not a bug, security, or nonconformance
claim.

A Windows schema-v3 [reference artifact](evidence/README.md) is committed and
bound to its exact source revision. CI independently generates, verifies, and
privacy-scans fresh Windows and Ubuntu artifacts without uploading them.

The schema-v4 replay lane includes:

- LangGraph 1.2.9, checkpoint 4.1.1, SQLite checkpointer 3.1.0, and
  sqlite-vec 0.1.9 under `durability="sync"` and strict msgpack;
- four scenarios repeated for ten rounds, with a fault worker and resume worker
  in separate processes for every round;
- 60 normalized mutating-call observations across 80 completed worker records;
- blind `write_file` and `edit_file` replay controls, committed-state
  reconciliation, and a tampered-state `UNRESOLVED` control;
- phase-bound event enums, public checkpoint-state summaries, and S0/S1/S2/S3
  fail-closed relative byte trees;
- an exact eight-file schema-v4 artifact and an independent offline verifier
  that imports no LangGraph, MCP execution, Node, or SQLite code;
- no model or paid-service call.

The registered failure is an exception after the first MCP mutation succeeds
and its MCP context closes, but before the LangGraph task returns. It is not a
hard crash, process kill, power-loss experiment, or SQLite crash-consistency
test. A commit-bound Windows
[reference artifact](evidence/README.md) is bundled for offline verification.
Public CI is configured to regenerate the lane independently on Windows and
Ubuntu; the repository does not treat configuration alone as a passing result.

The schema-v5 coding-agent lane includes:

- mini-swe-agent 2.4.6 using its `DefaultAgent`, `DeterministicModel`, and
  `LocalEnvironment`;
- one registered synthetic calculator repository and Git patch;
- `clean`, blind restart, journal-plus-byte-tree reconciliation, and tampered
  `UNRESOLVED` scenarios, each repeated for three rounds;
- one application-level fault during the first trajectory save, after the
  registered mutation command and journal record;
- S0/S1/S2/S3 fail-closed relative byte trees, changed-path projections, and
  harness-owned validation results;
- a SQLite WAL/FULL journal outside the Git workspace that records whether the
  exact command executed, was reconciled without execution, or remained
  unresolved;
- an exact mini-swe-agent wheel size/SHA-256 gate, selected installed-runtime
  file hashes, and a 93-version Python 3.12 constraint snapshot;
- schema-v5 canonical JSON, JUnit, manifest, and a separate offline verifier;
- zero model API and paid-service calls.

A Git diff or passing test is not a durable-effect fact. Reconciliation
requires both the exact prior journal record and the exact registered workspace
postcondition. The public artifact excludes raw trajectory, command text,
workspace, journal database, wheel, paths, environment, hostnames, model
messages, and process output. The lane is not a coding benchmark, agent
capability result, sandbox, or production recovery claim.

A commit-bound Windows
[reference artifact](evidence/README.md) is bundled for offline verification.
It is an author-generated local observation, not independent reproduction.
Public CI is configured to regenerate the lane on Windows and Ubuntu without
uploading its temporary work or artifact; the check status determines whether
those fresh runs passed.

## Quick start

Python 3.11 or newer is required.

Windows:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e ".[dev]"
.venv\Scripts\effect-witness run `
  --output-dir artifacts\run-1 `
  --source-revision UNCOMMITTED
.venv\Scripts\effect-witness verify --artifact-dir artifacts\run-1
```

POSIX:

```bash
python -m venv .venv
.venv/bin/python -m pip install -e ".[dev]"
.venv/bin/effect-witness run \
  --output-dir artifacts/run-1 \
  --source-revision UNCOMMITTED
.venv/bin/effect-witness verify --artifact-dir artifacts/run-1
```

The output directory must be absent. A committed run should replace
`UNCOMMITTED` with the 40-character source commit.
The schema-v2 producer removes its private work directory and writes no result,
summary, JUnit, or manifest files if any registered scenario misses its
expectation; the requested output directory can remain empty.

The exact real-filesystem lane additionally requires Node 24.18.0 and npm
11.16.0. Dependency preparation uses only the tracked lockfile with `npm ci`,
disables lifecycle scripts, audit, funding, and update checks, and isolates npm
configuration and cache from user configuration:

```powershell
.venv\Scripts\python scripts\prepare_filesystem_server.py `
  --output-dir .real-filesystem-deps
.venv\Scripts\effect-witness run-filesystem `
  --output-dir artifacts\real-filesystem `
  --dependency-dir .real-filesystem-deps `
  --source-revision UNCOMMITTED
.venv\Scripts\effect-witness verify-filesystem `
  --artifact-dir artifacts\real-filesystem
```

POSIX uses the same arguments with `.venv/bin/python`,
`.venv/bin/effect-witness`, and `/` separators. Dependency preparation requires
registry access; running and verifying the prepared lane do not invoke npm.
The prepared dependency directory is external runtime material and must not be
committed or copied into a Python distribution. Both real-lane output
directories must be absent. Each is built in a same-parent staging directory,
checked, and atomically renamed; a failed run is not published as an artifact.
At launch, the harness rechecks the tracked lock bytes and the registered seven
server-distribution files. It does not rehash every installed transitive
`node_modules` file, so the evidence does not prove runtime integrity of the
entire installed dependency tree.

The replay lane uses the same prepared filesystem dependency and additionally
requires the exact Python version-constraint snapshot. The runner rechecks its
bytes and every applicable installed version. The snapshot is not a
cross-platform hash lock:

```powershell
.venv\Scripts\python -m pip install `
  --constraint integrations\langgraph\constraints.txt `
  -e ".[dev,langgraph-replay]"
.venv\Scripts\python scripts\prepare_filesystem_server.py `
  --output-dir .replay-filesystem-deps
.venv\Scripts\effect-witness run-replay `
  --constraints-file integrations\langgraph\constraints.txt `
  --output-dir artifacts\langgraph-replay `
  --dependency-dir .replay-filesystem-deps `
  --source-revision UNCOMMITTED
.venv\Scripts\effect-witness verify-replay `
  --artifact-dir artifacts\langgraph-replay
```

POSIX uses the corresponding `.venv/bin/` executables and `/` separators.
Replay supports only audited x86-64 Windows/Linux environments with CPython
3.11-3.13. Dependency, output, and optional work paths must be mutually
disjoint; output and work targets must start absent and must never point at
user data. `--source-revision` is recorded as
`declared_source_revision`; the runner does not authenticate it.

The coding-agent lane requires CPython 3.12 and its own exact constraint
snapshot. Dependency preparation downloads only the registered
`mini_swe_agent-2.4.6-py3-none-any.whl`, verifies its exact 115,037-byte size
and SHA-256
`a35463c553ac825c7773b03cfa69cd44958e3af20155dcc5711fdf9e4c67cd54`,
and atomically publishes a one-file dependency directory:

```powershell
.venv\Scripts\python -m pip install --no-deps -e .
.venv\Scripts\python scripts\prepare_coding_agent.py `
  --output-dir .coding-agent-deps
.venv\Scripts\python -m pip install `
  --only-binary=:all: `
  --constraint integrations\mini-swe-agent\constraints-py312.txt `
  -e ".[dev]" `
  litellm==1.91.1 `
  .coding-agent-deps\mini_swe_agent-2.4.6-py3-none-any.whl
.venv\Scripts\effect-witness run-coding-agent `
  --constraints-file integrations\mini-swe-agent\constraints-py312.txt `
  --dependency-dir .coding-agent-deps `
  --output-dir artifacts\coding-agent `
  --source-revision UNCOMMITTED
.venv\Scripts\effect-witness verify-coding-agent `
  --artifact-dir artifacts\coding-agent
```

POSIX uses the corresponding `.venv/bin/` executables and `/` separators. The
93-version constraint snapshot has SHA-256
`a2a4b3cf0af75c357e1e4578d0cc4b0ffa222dcb9358a0b60a4e3a47512196eb`;
it is a version snapshot, not a cross-platform hash lock. Dependency, output,
and optional work directories must be mutually disjoint and must start absent.
Preparation requires access to the registered PyPI wheel URL; running and
verifying a prepared lane do not require a model or paid service.

Run the generic privacy scan in a clean checkout before installing dependencies
or creating build output, then run the remaining development gates:

```text
python scripts/privacy_scan.py .
python -m pytest
python -m ruff check --no-cache src tests scripts
python -m ruff format --check --no-cache src tests scripts
python -m build
python scripts/verify_distribution_boundary.py dist
```

## What verification means

`effect-witness verify` checks schema-v2 artifacts:

- regular-file inventory, safe relative paths, file-size limits, and complete
  manifest coverage;
- SHA-256 integrity for every evidence file;
- strict JSON parsing, exact registered field sets, and type-sensitive values;
- the exact schema-v2 scenario set and registered result matrix;
- each registered tool's complete annotation object and exact input schema;
- the exact canonical hash of each registered write argument object;
- registered response completion/error states, write-response facts,
  reconciliation facts, causal client-journal event sequences and decision
  payloads, fault modes, attempt states, effect counts, and the synchronized
  concurrency witness;
- JUnit and summary relationships.

Verification uses one bounded byte snapshot per artifact invocation. The
verifier rejects files that change identity or version while that snapshot is
being captured, rather than hashing and interpreting separate reads.

The manifest is not a signature. Replacing every file and the manifest still
requires an external trusted Git commit or release digest to detect.

`effect-witness verify-filesystem` independently checks schema-v3 inventory,
manifest closure, exact dependency and descriptor registrations, safe relative
byte-tree shapes and hashes, registered S0/S1/S2 relationships, response
redaction shapes, platform-bounded observations, JUnit, and summary
relationships. It imports no execution runner.

`effect-witness verify-replay` independently checks schema-v4 exact file and
directory inventory, manifest closure, frozen dependency/provenance facts,
type-sensitive process and checkpoint summaries, phase-bound event sequences,
normalized call shapes, registered S0/S1/S2/S3 relationships, canonical JUnit,
and cross-file counts for all 40 rounds. It does not execute or import the
replay stack, inspect a checkpoint database, or prove artifact authenticity.

`effect-witness verify-coding-agent` independently checks schema-v5 exact
inventory, manifest closure, registered dependency/provenance facts,
type-sensitive worker summaries, journal projections, command-execution
decisions, S0/S1/S2/S3 byte trees, changed paths, harness-owned validation
results, JUnit, and cross-file counts for all 12 rounds. It does not import or
execute mini-swe-agent, run Git or tests, open the private journal, or prove
artifact authenticity.

See [architecture](docs/architecture.md), the
[schema-v2 reference](docs/evidence-schema-v2.md), and the
[schema-v3 filesystem reference](docs/evidence-schema-v3-filesystem.md), and
the [schema-v4 replay contract](docs/evidence-schema-v4-langgraph-replay.md),
and the
[schema-v5 coding-agent contract](docs/evidence-schema-v5-mini-swe-agent.md).

## Privacy gate

The repository scanner covers common path, contact, key, token, phone, and
public-IP patterns in UTF-8 content up to 2 MiB and in filenames or relative
paths. NUL-containing, non-UTF-8, oversized UTF-8, and unreadable files become
structured failures instead of being silently skipped. When a path itself
matches, the report uses `<redacted-path>`.

The scanner traverses every ordinary file and directory under its root,
including development caches and build outputs. Only a verified ordinary
root-level `.git` directory is skipped. A publication candidate therefore
removes generated residues first, then audits reachable Git objects plus
commit and tag metadata as a separate release gate.

The CI command uses the generic patterns and reports that a private denylist is
not enforced. Publication additionally requires an unpublished, external
literal denylist without printing its matched values:

```text
python scripts/privacy_scan.py . \
  --denylist-file <external-local-file> \
  --require-denylist
```

This is a publication guard, not a general secret-scanning or data-loss
prevention product.

## Related work boundary

EffectWitness is not a transaction runtime, side-effect guard, or generic
response-fault dashboard. [Atomix](https://github.com/mpi-dsg/atomix),
[Replaysafe](https://github.com/JobGuards/Replaysafe),
[OnceOnly](https://www.onceonly.tech/),
[AgentCheck](https://github.com/aritra741/AgentCheck), the
[official MCP conformance framework](https://github.com/modelcontextprotocol/conformance),
and the [A2A TCK](https://github.com/a2aproject/a2a-tck) are explicit
comparison points.

The bounded comparison and inspected revisions are documented in
[related work](docs/prior-art.md). No third-party source code is included.

## Development and security

CI is configured for Python 3.11-3.13 on current GitHub-hosted Ubuntu and
Windows runners. Separate Windows/Ubuntu jobs prepare dependencies from the
exact tracked Node/npm lock, run schema v3 or schema v4, verify offline, and
scan each ephemeral artifact without uploading it. A configured job is not
reported as passing until the public run is green. The synthetic fixture
contains deliberate process exits and must remain loopback-only. Read
[SECURITY.md](SECURITY.md) before changing either transport boundary and
[CONTRIBUTING.md](CONTRIBUTING.md) before submitting changes.

Schema v5 is narrower: CPython 3.12 on x86-64 Windows/Linux only. Its
`LocalEnvironment` executes a real shell command inside a newly owned synthetic
workspace and is not a security sandbox. A documented command or configured CI
job is not itself evidence that a schema-v5 run passed.

## License

Original code in this repository is licensed under Apache-2.0. Dependency
licenses remain their own; see [third-party notices](THIRD_PARTY_NOTICES.md).
