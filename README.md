# EffectWitness

EffectWitness is a pre-alpha, local-first protocol experiment for one narrow
question:

> When an agent tool declares an effect-related hint, do a client's observations
> and the bundled fixture's durable synthetic effect facts match that declaration
> under repeated or threaded calls, response loss, process exit, and restart?

It deliberately separates three fact domains:

1. the metadata and input schema returned by the protocol;
2. what the client observed and decided;
3. what the controlled fixture durably recorded.

The current adapter targets MCP tool annotations. The
[official MCP explanation](https://blog.modelcontextprotocol.io/posts/2026-03-16-tool-annotations/)
describes these annotations as untrusted hints, so EffectWitness never treats a
mismatch as automatic protocol nonconformance. Its result vocabulary is
`MATCH`, `MISMATCH`, `UNRESOLVED`, and `NOT_APPLICABLE`.

## Status and evidence boundary

This repository is an early candidate under active pre-alpha development. It
has no verified external users, adoption, independent reproduction, third-party
review, production deployment, or recruiting outcome.

The current implementation is a controlled dual-view fixture, not a general
black-box observer for arbitrary third-party tools. It uses synthetic effects,
loopback MCP Streamable HTTP, separate client and server SQLite databases, and
deterministic test faults.

It does **not** establish exactly-once execution, official MCP certification,
distributed consistency, security, production reliability, model capability,
framework superiority, or external usefulness. See the full
[claim boundary](docs/claims.md).

## Implemented reproducible slice

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

The output directory must be absent or empty. A committed run should replace
`UNCOMMITTED` with the 40-character source commit.

Run the development gates:

```text
python -m pytest
python -m ruff check --no-cache src tests scripts
python -m ruff format --check --no-cache src tests scripts
python scripts/privacy_scan.py .
python -m build
```

## What verification means

`effect-witness verify` checks:

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

See [architecture](docs/architecture.md) and the
[schema-v2 reference](docs/evidence-schema-v2.md).

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

CI is configured for Python 3.11–3.13 on current GitHub-hosted Ubuntu and
Windows runners. The fixture contains deliberate process exits and must remain
loopback-only. Read [SECURITY.md](SECURITY.md) before changing its transport
boundary and [CONTRIBUTING.md](CONTRIBUTING.md) before submitting changes.

## License

Original code in this repository is licensed under Apache-2.0. Dependency
licenses remain their own; see [third-party notices](THIRD_PARTY_NOTICES.md).
