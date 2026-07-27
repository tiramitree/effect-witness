# Reference evidence

`reference-v0.1.0` is the bundled schema-v2 reference artifact for the
controlled ten-scenario matrix.

- source revision:
  `f4575f88cf6a17f6c32bd2c7462063142d37c56a`
- artifact manifest SHA-256:
  `abf887a809460020aed24819b5d2bebf8ec68e12dc64ad8a9e760595b6837abc`
- registered results: 3 `MATCH`, 4 `MISMATCH`, and 3 `NOT_APPLICABLE`
- evidence scope: synthetic local SQLite effects over loopback MCP Streamable
  HTTP
- model API calls: 0
- paid-service calls: 0

The artifact was generated on Windows with CPython 3.12.10 from the installed
EffectWitness 0.1.0 wheel built from the source revision above. Run:

```text
effect-witness verify --artifact-dir evidence/reference-v0.1.0
```

Verification checks offline integrity and internal consistency. The manifest
is not a publisher signature, and this artifact does not establish production
reliability, security, official protocol conformance, external adoption, or
performance.

`reference-v0.2.0-filesystem-windows` is the bundled schema-v3 observation of
the official filesystem server over stdio.

- source revision:
  `8b8bc6131d864b8eaa966a72455ba86817f88a22`
- artifact manifest-file SHA-256:
  `ad883b9823f61f3b79e0abd40b1533c5634f246ce86427063845e01c03562101`
- inventory: 10 files, 18,605 bytes
- registered scenarios: 5, with two calls per scenario
- registered outcomes: 2 repeated-idempotent, 1 read-only, 1 error with no
  visible byte-tree effect, and 1 repeat error after one visible effect
- runtime: Windows, CPython 3.12.10, Node 24.18.0
- model API calls: 0
- paid-service calls: 0

Run:

```text
effect-witness verify-filesystem \
  --artifact-dir evidence/reference-v0.2.0-filesystem-windows
```

The artifact records only normalized hashes, bounded facts, relative byte-tree
observations, JUnit, and a manifest. It excludes generated fixture content,
absolute paths, environment, hostnames, ports, raw tool text, raw mutating
responses, server logs, npm packages, and `node_modules`.

This is one source- and OS-bound local observation, not independent
reproduction, package-wide correctness, official conformance, security,
production behavior, external review, or adoption. CI separately generates,
verifies, and privacy-scans fresh Windows and Ubuntu artifacts without
uploading them. The schema and reproduction boundary are documented in
[`docs/evidence-schema-v3-filesystem.md`](../docs/evidence-schema-v3-filesystem.md).

`reference-v0.3.0-langgraph-replay-windows` is the bundled schema-v4
observation of the registered LangGraph replay lane.

- declared source revision:
  `d591710356454aa280237874ee8d8f3bec6e705a`
- artifact manifest-file SHA-256:
  `85de70218b2c29696c03b9061c0ede74c81de959b0f50c4ee7a6c4c5eaf1f5d1`
- inventory: 8 files, 190,762 bytes
- registered execution: 4 scenarios x 10 rounds
- completed worker records: 80
- normalized mutating-call observations: 60
- runtime: Windows x86-64, CPython 3.12.10, Node 24.18.0
- model API calls: 0
- paid-service calls: 0

Run without the optional replay execution dependencies:

```text
effect-witness verify-replay \
  --artifact-dir evidence/reference-v0.3.0-langgraph-replay-windows
```

The artifact contains normalized phase/event enums, process and public
checkpoint-state summaries, call shapes, decisions, S0/S1/S2/S3 relative
byte-tree facts, JUnit, provenance, and a manifest. It excludes checkpoint and
journal databases, WAL/SHM files, raw checkpoint rows, fixture bytes, absolute
paths, environment, hostnames, ports, PIDs, timestamps, raw tool
arguments/responses, exception messages, worker output, server logs, npm
packages, runtimes, and `node_modules`.

This is one source-, version-, input-, and OS-bound local observation. It does
not establish exactly-once execution, arbitrary workflow or MCP correctness,
official conformance, crash consistency, production recovery, distributed
consistency, general reconciliation correctness, model/agent capability,
performance, security, external review, reproduction, adoption, deployment,
or recruiting outcomes. The source revision is caller-declared inside the
artifact; the offline verifier checks integrity and internal consistency, not
publisher authenticity. The schema and reproduction boundary are documented
in
[`docs/evidence-schema-v4-langgraph-replay.md`](../docs/evidence-schema-v4-langgraph-replay.md).
