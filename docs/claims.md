# Claim boundary

This file is the public claim contract for the current pre-alpha candidate.

## Supported by the bundled reproducible slice

- The suite starts a separate MCP fixture process over loopback Streamable
  HTTP.
- For repeated writes, the client journals the registered canonical argument
  hash. The verifier binds the complete annotation object and exact tool input
  schema for each registered tool.
- The bundled SQLite fixture can demonstrate truthful and deliberately
  misleading `idempotentHint` and `readOnlyHint` examples.
- The MCP client adapter distinguishes transport failures from completed MCP
  `isError=true` responses. That branch is unit-tested; no current registered
  artifact scenario produces `isError=true`.
- In the registered synthetic scenarios, client observations, client decisions,
  server attempts, server fault modes, and durable synthetic effect counts are
  exported separately.
- The eight-call concurrent controls require all eight client workers to pass
  one barrier and record a maximum of eight in-flight workers before calls are
  accepted as concurrent evidence.
- The offline verifier rejects missing files, hash changes, unsafe paths,
  declaration or schema drift, non-registered request hashes, missing or
  contradictory client decisions, inconsistent reconciliation facts, false
  evidence checks, altered effect counts, and cross-file inconsistencies
  covered by schema v2.

These statements apply only to the exact bundled code, recorded direct
dependency versions, synthetic data, loopback transport, and registered scenarios.

## Supported by the schema-v3 real-implementation lane

- The lane uses Python MCP SDK 1.28.1 over stdio to
  `@modelcontextprotocol/server-filesystem` version `2026.7.10`, prepared by
  `npm ci` from the tracked lock under Node 24.18.0; that lock resolves the
  JavaScript SDK to 1.29.0.
- Dependency preparation runs only `npm ci` with lifecycle scripts disabled and
  isolated empty npm user/global configuration. Before execution, the harness
  rechecks the tracked lock bytes and rejects any installed server distribution
  that differs from the registered seven-file size/SHA-256 set. It does not
  rehash every transitive `node_modules` file.
- The exact tool descriptors observed for `read_text_file`,
  `create_directory`, `write_file`, and `edit_file` matched the registered
  annotation objects and description/descriptor hashes.
- For five registered inputs, two calls are bracketed by S0/S1/S2 fail-closed
  relative byte-tree observations. The read, simple-create, and write inputs
  matched their narrow read-only or repeated-idempotent expectations.
- The registered repeated edit produced one visible byte-tree change, then an
  error with no second visible change.
- On the registered Windows environment, nested create produced an MCP error
  twice and no visible byte-tree change. Linux accepts only that observation or
  creation of the exact two nested directories. This is a neutral
  OS/input/version-bounded observation.
- The strict schema-v3 verifier rejects inventory, manifest, provenance,
  descriptor, stimulus, call-shape, byte-tree, platform, JUnit, and summary
  drift covered by its frozen registration.
- The Python wheel excludes `integrations/`; both Python distributions exclude
  `node_modules`, npm tarballs, and Node runtime payloads.

These statements apply only to the exact versions, registered inputs,
single-process stdio session, ordinary relative byte trees, and Windows/Linux
CI boundary above. The committed schema-v3 reference is one Windows observation
bound to its exact source revision. CI generates fresh Windows and Linux
observations ephemerally without publishing their artifacts.

## Supported by the schema-v4 LangGraph replay lane

- The lane fixes LangGraph 1.2.9, checkpoint 4.1.1, SQLite checkpointer 3.1.0,
  sqlite-vec 0.1.9, MCP Python 1.28.1, Node 24.18.0, and the schema-v3
  filesystem registration under synchronous durability and strict msgpack.
- Before worker launch, the runner checks the exact 58-package constraint
  snapshot bytes and every applicable installed Python distribution version.
  The snapshot is a version constraint, not a cross-platform hash lock.
- Four scenarios run for ten rounds each. Every round uses separate fault and
  resume Python processes, yielding 80 worker records and 60 normalized
  mutating-call observations when the complete matrix passes.
- The registered exception follows the first successful MCP mutation and MCP
  context closure but precedes task return. The fault worker exits with code 17;
  this is not a hard-crash or power-loss boundary.
- After the fault, the public LangGraph state API must report one checkpoint
  history item and `next=["workflow"]`. After resume it must report two history
  items and an empty next-task list.
- Blind write performs a second successful mutating call without a second
  visible tree change. Blind edit performs a second call that returns an MCP
  error without a second visible tree change.
- The exact reconciliation control confirms the registered committed
  postcondition without another mutation. The tampered control returns
  `UNRESOLVED` without changing the intervened state.
- Each round exports phase-bound event enums, normalized process/call facts, and
  S0/S1/S2/S3 relative byte trees. The eight-file artifact excludes private
  checkpoint/journal state and raw runtime material.
- The independent verifier recomputes the frozen 40-round relationships from
  one bounded snapshot without importing or executing LangGraph, MCP execution,
  Node, or SQLite.

These statements are limited to the exact versions, x86-64 Windows/Linux,
CPython 3.11-3.13, four inputs, one post-effect exception location, one
byte-tree postcondition, local filesystem sandboxes, and the documented
fresh-dependency preparation procedure. The artifact labels its source
revision as caller-declared; an external trusted Git or release digest is
required for authenticity.

The bundled schema-v4 Windows reference is one local observation bound to
source revision `b99fa745cc98dd543dcd637d3523eabba864552e`. The earlier
0.3.0 observation remains bundled under its own source binding. CI is configured
to generate fresh Windows and Linux observations ephemerally without uploading
them; public CI status, rather than this sentence, determines whether a
particular run passed.

## Supported by the schema-v5 mini-swe-agent lane

- The lane uses mini-swe-agent 2.4.6 `DefaultAgent`,
  `DeterministicModel`, and `LocalEnvironment` with zero model API and
  paid-service calls.
- The dependency gate requires the exact 115,037-byte
  `mini_swe_agent-2.4.6-py3-none-any.whl` with SHA-256
  `a35463c553ac825c7773b03cfa69cd44958e3af20155dcc5711fdf9e4c67cd54`.
  The upstream wheel metadata reports MIT, Python `>=3.10`, and an Alpha
  development-status classifier.
- The runner checks a 93-version CPython 3.12 constraint snapshot with SHA-256
  `a2a4b3cf0af75c357e1e4578d0cc4b0ffa222dcb9358a0b60a4e3a47512196eb`
  and the registered selected mini-swe-agent runtime-file bytes. The constraint
  snapshot is not a cross-platform hash lock.
- Four scenarios run for three rounds each on registered x86-64 Windows or
  Linux with CPython 3.12. Every round starts from one exact synthetic Git
  repository and targets one exact patch and test command.
- The registered fault occurs during the first trajectory save after the
  initial mutation command and out-of-workspace WAL/FULL journal write. It is
  an application-level exception, not a hard crash, native mini-swe-agent
  resume, power loss, or filesystem crash-consistency boundary.
- The clean scenario executes the registered mutation once. Blind restart
  executes the command again and observes the registered nonzero return code
  with no second byte-tree change.
- The reconcile scenario requires both the exact initial journal row and exact
  registered post-patch byte tree, then records `RECONCILED` without another
  command execution. The tampered scenario records `UNRESOLVED` without
  executing the command.
- Git changed paths and harness-owned validation results are exported
  separately from the durable journal projection. Neither a workspace diff nor
  a passing test is treated alone as proof of a persisted external effect.
- The strict schema-v5 verifier checks exact inventory, manifest closure,
  dependency/provenance facts, worker summaries, journal decisions,
  S0/S1/S2/S3 byte trees, changed paths, validation outcomes, JUnit, and
  summary relationships without importing or executing mini-swe-agent.

These statements apply only to mini-swe-agent 2.4.6, its registered selected
runtime files, the exact deterministic model outputs, one synthetic Git patch,
one application-level trajectory-write fault, four scenarios, three rounds,
CPython 3.12, and x86-64 Windows/Linux. They do not extend to arbitrary coding
tasks, commands, repositories, agents, models, or operating-system behavior.
No bundled schema-v5 reference artifact or independent reproduction is claimed
until one is explicitly added and bound to a trusted public source revision.

## Explicitly not established

- Runtime integrity of the complete transitive `node_modules` tree.

- exactly-once execution;
- arbitrary LangGraph workflow correctness;
- hard-crash, power-loss, SQLite, or checkpointer crash consistency;
- production recovery or availability;
- reconciliation correctness beyond the exact registered byte-tree
  postcondition;
- official MCP certification or conformance status;
- security;
- production reliability or availability;
- distributed consistency;
- arbitrary third-party tool correctness;
- mini-swe-agent native resume or crash recovery;
- exactly-once execution for arbitrary coding commands;
- arbitrary coding-agent correctness or model repair ability;
- SWE-bench, ProgramBench, repository, or industry performance;
- safe sandboxing or general process-tree cleanup;
- Windows and Linux equivalence beyond the registered observations;
- package-wide correctness for the filesystem server;
- production filesystem behavior, permissions, timestamps, links, or
  concurrent mutation behavior;
- a verified rebuild from the npm registry metadata `gitHead`;
- model or agent capability;
- long-context, long-term-memory, or multi-agent behavior;
- performance or scale;
- framework superiority;
- external users, adoption, review, reproduction, deployment, or recruiting
  outcomes.

`MATCH` means that the registered observation matched the narrow declared
effect expectation. `MISMATCH` is expected for deliberately misleading
negative controls. `NOT_APPLICABLE` means the scenario does not exercise the
relevant repeat-effect contract. None of these labels is a protocol violation
ruling.

The schema-v3 outcome names are observation labels, not protocol verdicts.
In particular, an error/no-effect result is not described as a bug,
vulnerability, or nonconformance.

## Evidence versus declaration

The artifact fields `model_api_calls=0` and `paid_service_calls=0` are declared
run metadata. The repository design does not contain model or paid-service
clients, but the artifact itself is not a packet-capture proof of all machine
network activity.

The manifest proves integrity relative to itself, not publisher authenticity.
Use a trusted Git commit, release digest, or other external root when
authenticity matters.
