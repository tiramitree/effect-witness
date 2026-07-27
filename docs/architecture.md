# Architecture and trust boundaries

EffectWitness has three isolated evidence lanes. Schema v2 compares what an MCP
client observed with what the bundled fixture durably recorded. Schema v3
observes an exact external implementation through byte-tree snapshots. Schema
v4 observes one exact workflow replay boundary across separate Python
processes. None is a general black-box verdict on arbitrary third-party tools
or frameworks.

```text
scenario runner
  |
  +-- client journal (SQLite, WAL/FULL)
  |
  +-- MCP Streamable HTTP over 127.0.0.1
        |
        +-- isolated fixture process
              |
              +-- one-shot launch fault controller
              |
              +-- server-side effect facts (SQLite, WAL/FULL)
```

The schema-v3 lane has a different boundary:

```text
tracked package.json + exact package-lock.json
  |
  +-- isolated npm ci --ignore-scripts
        |
        +-- exact seven-file server distribution check
              |
              +-- Python MCP 1.28.1 client over stdio
                    |
                    +-- exact filesystem server 2026.7.10
                          |
                          +-- per-scenario temporary sandbox
                                |
                                +-- relative byte trees S0 / S1 / S2
```

Its client resolves the registered Node executable before launch. The server
receives only the platform variables needed to start, with no inherited user
path, proxy, token, or credential variables. Stderr is sent directly to the
null device. Absolute sandbox, dependency, entrypoint, and executable paths
exist only in process memory; they are not evidence fields or hashed evidence
inputs.

The launch gate rechecks the tracked lock bytes and exact seven-file server
distribution. It does not rehash the full transitive `node_modules` tree, so
the lock records dependency resolution while the stronger runtime byte claim
is limited to those seven server files.

The schema-v4 lane adds a separate workflow boundary:

```text
exact Python constraints + exact filesystem registration
  |
  +-- schema-v4 orchestrator
        |
        +-- fault worker process
        |     +-- LangGraph entrypoint/task + SQLite checkpointer
        |     +-- MCP stdio mutation
        |     +-- registered post-effect/pre-return exception
        |
        +-- S1 capture / optional registered S2 intervention
        |
        +-- resume worker process with the same thread/checkpoint
              +-- blind replay or byte-tree reconciliation
              +-- S3 capture
  |
  +-- remove the exact owned checkpoint/journal work root
  +-- seal one normalized eight-file artifact
```

Workers launch with Python isolated mode, an owned case-root working directory,
no user site, no inherited proxy/token/credential variables, and separate
process groups. The runner rejects overlapping output, dependency, and custom
work paths before creating a directory. Interruption and failure paths attempt
every exact owned-root cleanup independently.

The runner binds the constraint snapshot bytes and all applicable installed
Python versions. The snapshot is not a wheel hash lock. The filesystem launch
gate retains schema v3's exact seven-file server check and tracked JavaScript
lock boundary; it still does not hash every transitive installed JavaScript
file.

Raw tool text, descriptor descriptions, server logs, environment, and raw
mutation responses are not retained. Read content is represented only by byte
length and SHA-256. Mutation calls retain only a registered response shape.
Filesystem state is captured as sorted relative directory entries and file
length/SHA-256 records. Snapshotting rejects unsafe relative paths,
non-regular files, symlinks or reparse points, oversized files, and identity or
version changes during capture.

Dependency and artifact final paths must be absent and below an ordinary
non-reparse parent chain. Each operation owns a fresh same-parent staging
directory. A complete dependency tree or manifested artifact is atomically
renamed to its final path; failures remove only the exact staging/work roots
created by that invocation and do not publish a partial final directory.

## Schema-v2 fact domains

1. Declaration: the MCP tool descriptor returned over the transport, including
   annotations and input schema.
2. Client observation: send, response, error, reconciliation, and decision
   records in a client-owned SQLite journal.
3. Server fact: attempt and synthetic effect rows durably committed by the
   fixture.

The exported result keeps these domains separate. A label is recomputed from
their relationship; it is not copied from the fixture.

## Harness controls are not tool arguments

The protocol-visible write arguments are only:

```json
{"operation_id": "op-1", "payload": {"value": 1}}
```

Attempt identities are allocated by the server-side store. A one-shot fault is
selected when the fixture process starts and consumed internally by its first
write. The verifier requires the exact registered input schema, which contains
neither `attempt_id` nor `fault_mode`.

The fixture is restricted to `127.0.0.1`. The client ignores proxy environment
variables. Parent readiness requires a successful MCP call that returns a
per-launch random nonce; an arbitrary listener accepting the TCP port is not
enough.

## Synthetic fault points

- `pre_commit_exit`: the process exits after durable attempt receipt but before
  an effect commit.
- `post_commit_delay`: the effect commits, then the response is delayed past a
  short client read timeout.
- `post_commit_exit`: the effect commits, then the process exits before a
  successful response is observed.

The two eight-call scenarios use an eight-party client barrier. Their exported
concurrency witness records all eight workers passing the barrier and a maximum
of eight in-flight workers. This is a controlled local overlap fact, not a
production throughput or distributed-concurrency claim.

Non-clean faults require explicit test mode. This fixture intentionally kills
its own process and must never be treated as a production server.

## SQLite model

The server database contains attempts, effects, stable-operation bindings, and
an append-only audit sequence. Writes use `BEGIN IMMEDIATE`; each effect is
uniquely bound to one attempt. A stable operation key is bound to its canonical
payload hash.

The client database is separate. It records canonical request hashes and
response hashes, not local paths or exception messages. Both databases fail
closed if SQLite cannot enable WAL journaling and `synchronous=FULL`.

SQLite is being used here to exercise a local durability and contention
boundary. These results do not establish distributed consistency.

## Artifact verification

`effect-witness verify` performs four layers of offline checks:

1. safe path, regular-file, per-file, and total-size inventory;
2. one bounded byte snapshot with file identity/version checks, then complete
   SHA-256 manifest closure over those exact bytes;
3. strict JSON, exact registered field and value types, schema-v2 scenario,
   causal journal and decision, complete registered annotation/input-schema,
   exact request, reconciliation, concurrency, fault, attempt, effect,
   response, JUnit, and summary invariants;
4. registered ten-scenario matrix validation.

The manifest is not signed. If an attacker replaces both every file and the
manifest, an external trusted digest or source revision is still required to
detect that replacement.

Schema v3 uses a distinct entry point and verifier. The verifier imports the
frozen registration and pure scenario semantics, but not the execution runner.
It takes one bounded artifact snapshot, requires the exact ten-file inventory
(nine entries plus the manifest), and recomputes manifest closure, result
shapes, byte-tree hashes, S0/S1/S2 relationships, tool and dependency
registrations, JUnit, and summary counts.
Schema-v2 verification remains unchanged and does not accept schema-v3
artifacts.

The v3 provenance binds an npm registry-metadata report, the tracked lock, and
the exact installed server-file set. It does not bind every transitive installed
file. The reported `gitHead` is not represented as a verified rebuild from
source.

Schema v4 has another distinct entry point and verifier. Its artifact contains
only normalized phase/event enums, process exit and public checkpoint-state
summaries, mutating-call shapes, decisions, and S0/S1/S2/S3 relative byte
trees. Private checkpoint and journal databases are deleted before artifact
files are written.

The v4 verifier imports the frozen registration but neither runner nor worker.
It reads one bounded snapshot, requires the exact two-directory/eight-file
topology, and independently recomputes all 40 round relationships. It never
opens a checkpoint database or executes LangGraph, MCP, Node, or SQLite. The
recorded source revision is explicitly caller-declared; the manifest and
verifier do not authenticate a publisher.
