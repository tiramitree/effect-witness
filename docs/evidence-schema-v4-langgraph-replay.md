# Schema v4: LangGraph replay across registered MCP effects

Schema v4 is a separate artifact and verifier. It does not reinterpret the
schema-v2 fixture or schema-v3 repeated-call observations.

## Registered execution

The lane fixes:

- EffectWitness 0.4.0 for newly produced evidence; the offline verifier also
  accepts the registered 0.3.0, 0.3.1, 0.3.2, and 0.3.3 producers;
- LangGraph 1.2.9;
- langgraph-checkpoint 4.1.1;
- langgraph-checkpoint-sqlite 3.1.0;
- sqlite-vec 0.1.9;
- Python MCP SDK 1.28.1;
- Node 24.18.0;
- `@modelcontextprotocol/server-filesystem` 2026.7.10;
- JavaScript MCP SDK 1.29.0 through the tracked npm lock;
- `durability="sync"` and `LANGGRAPH_STRICT_MSGPACK=true`;
- x86-64 Windows or Linux and CPython 3.11-3.13.

`integrations/langgraph/constraints.txt` is an exact 58-package
version-constraint snapshot. Its SHA-256 and package count are registered, and
the runner checks every applicable installed distribution before launching a
worker. It is not a cross-platform hash lock and does not prove the bytes of
each installed dependency.

The filesystem dependency must be prepared from the tracked npm lock with the
repository script. At launch, the harness rechecks the lock and the exact seven
files in the filesystem-server distribution. It does not hash every installed
transitive JavaScript file; a fresh `npm ci` is part of the registered
reproduction procedure.

## Four scenarios and four states

Each scenario runs for exactly ten rounds. Every round starts a fault worker,
waits for it to exit, and starts a separate resume worker with the same
checkpoint thread.

| Scenario | Resume policy | Registered observation |
|---|---|---|
| `write_blind` | blind | A second `write_file` call succeeds; the visible tree has no second change |
| `edit_blind` | blind | A second `edit_file` call returns an MCP error; the visible tree has no second change |
| `edit_reconcile` | byte-tree reconciliation | The registered postcondition is confirmed as committed; no second mutating call is made |
| `edit_reconcile_tampered` | byte-tree reconciliation | The registered external intervention makes the postcondition indeterminate; resume returns `UNRESOLVED` without another mutation |

The four snapshots have one definition across every scenario:

- S0: immediately before the fault worker;
- S1: after the fault worker exits;
- S2: immediately before the resume worker; the registered intervention for
  the tampered scenario occurs between S1 and S2;
- S3: after the resume worker completes.

These are call and relative byte-tree observations. “No second visible change”
does not mean no second call, no hidden effect, or exactly-once execution.

## Registered failure boundary

The injected exception occurs only after the first MCP mutation completed,
after the MCP context closed, and before the LangGraph task returned. The fault
worker emits one normalized record and exits with registered code 17. The
resume occurs in a new isolated Python process.

This is not a hard crash, forced process kill, power-loss test, or SQLite
crash-consistency test. Public event records contain only the registered
`phase` and event `type`; event payloads, sequence numbers, paths, process
identifiers, and times are not exported.

## Exact artifact

The artifact has exactly two directories (`.` and `results`) and eight regular
files:

```text
junit.xml
manifest.sha256
provenance.json
summary.json
results/edit_blind.json
results/edit_reconcile.json
results/edit_reconcile_tampered.json
results/write_blind.json
```

Each result object has exactly:

```text
all_registered_checks_met
policy
round_count
rounds
scenario_id
tool_name
```

Each round has exactly:

```text
all_checks_met
checks
decisions
events
fault_process
mutating_call_observations
resume_process
round
s0
s1
s2
s3
```

`fault_process.error_types` contains only the registered exception type name.
No message or traceback is retained. Checkpoint facts are derived from
LangGraph's public state API and contain only availability, history count, and
the registered next-task list.

The summary records 4 scenarios, 10 rounds each, 80 worker process records, and
60 normalized mutating-call observations. `declared_source_revision` is
caller-supplied, and `source_revision_verification` is fixed to
`caller_declared`; authenticity requires an external trusted Git commit or
release digest.

## JUnit and manifest

The JUnit suite is named `effect-witness-langgraph-replay`, with `tests="40"`
and `failures="0"`. Testcases are scenario-major, then rounds 01 through 10.
The classname is `effect_witness.langgraph_replay`, and each `system-out`
contains only canonical JSON such as:

```json
{"failed_checks":[],"round":1,"scenario_id":"write_blind"}
```

The producer writes and the verifier accepts only the registered canonical
JUnit bytes with an LF XML-declaration newline. The manifest generator writes
sorted relative paths, LF lines, and lowercase SHA-256 values. The verifier
checks safe unique paths, complete coverage, and hash closure; the manifest is
not a signature.

## Offline verifier

`effect-witness verify-replay`:

1. captures one bounded snapshot of the exact file and directory topology;
2. verifies complete manifest coverage and SHA-256 integrity;
3. parses strict JSON with type-sensitive equality;
4. independently recomputes every registered call, process, checkpoint,
   phase/event, S0/S1/S2/S3, summary, provenance, and JUnit relationship;
5. redacts unregistered artifact paths from diagnostics.

The verifier does not import or execute LangGraph, MCP execution code, Node, or
SQLite. It does not open a checkpoint or journal database and does not use the
producer's evaluator.

## Privacy and claim boundary

The artifact excludes checkpoint and event-journal databases, WAL/SHM files,
checkpoint rows, absolute paths, environment values, hostnames, ports, process
identifiers, timestamps, raw tool arguments or responses, raw worker output,
server logs, exception messages, fixture bytes, npm packages, `node_modules`,
and Node runtimes.

Schema v4 does not establish:

- exactly-once execution;
- arbitrary LangGraph workflow or MCP server correctness;
- official MCP certification or conformance;
- hard-crash, power-loss, SQLite, or checkpointer crash consistency;
- production recovery, availability, or filesystem behavior;
- concurrency or distributed consistency;
- reconciliation correctness beyond the registered byte-tree postcondition;
- model-driven agent, long-context, long-term-memory, or multi-agent behavior;
- performance, scale, security, or vulnerability status;
- source authenticity without an external trusted Git or release digest;
- external adoption, independent reproduction, review, deployment, or
  recruiting outcome.
