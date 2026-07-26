# Architecture and trust boundaries

EffectWitness v0 is a controlled dual-view experiment. It compares what an
MCP client observed with what the bundled fixture durably recorded. It is not
yet a black-box adapter for arbitrary third-party tools.

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

## Three separate fact domains

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
