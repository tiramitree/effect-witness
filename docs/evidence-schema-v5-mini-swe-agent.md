# Schema v5: mini-swe-agent coding reconciliation

Schema v5 is a separate artifact and verifier. It does not reinterpret the
schema-v2 fixture, schema-v3 filesystem observations, or schema-v4 LangGraph
replay evidence.

## Registered dependency and runtime boundary

The lane fixes:

- mini-swe-agent 2.4.6;
- its `DefaultAgent`, `DeterministicModel`, and `LocalEnvironment`;
- the exact 115,037-byte
  `mini_swe_agent-2.4.6-py3-none-any.whl`;
- wheel SHA-256
  `a35463c553ac825c7773b03cfa69cd44958e3af20155dcc5711fdf9e4c67cd54`;
- upstream wheel metadata reporting MIT, Python `>=3.10`, and an Alpha
  development-status classifier;
- a 93-version CPython 3.12 constraint snapshot with SHA-256
  `a2a4b3cf0af75c357e1e4578d0cc4b0ffa222dcb9358a0b60a4e3a47512196eb`;
- selected installed mini-swe-agent runtime-file size and SHA-256 values;
- x86-64 Windows or Linux and CPython 3.12.

The constraint snapshot is an exact version registration, not a
cross-platform wheel hash lock. The lane does not extend mini-swe-agent's
upstream Python `>=3.10` metadata into a claim that schema v5 supports every
such interpreter or platform.

The dependency preparation script downloads the one registered wheel without
using environment proxies, checks its filename, size, and SHA-256, then
atomically publishes a one-file dependency directory. The wheel is not
committed, copied into an EffectWitness distribution, or included in an
evidence artifact.

## Deterministic workload

Every round creates a new owned synthetic Git repository with one calculator
implementation, one test, and one registered patch. The deterministic model
provides exactly two registered actions:

1. apply the registered patch and run the fixed tests;
2. submit the registered result.

The exact command text remains registered in source but is not copied into the
public artifact. `CodingEffectAdapter` accepts only those two actions.
mini-swe-agent invokes the deterministic model locally; the lane performs zero
model API calls and zero paid-service calls.

`LocalEnvironment` executes a real shell command inside the newly owned
workspace. It is not a security sandbox and must never be pointed at user data,
an existing source repository, shared storage, or production state.

## Four scenarios and four snapshots

Each scenario runs for exactly three rounds.

| Scenario | Policy | Registered observation |
|---|---|---|
| `clean` | blind | The registered mutation executes once, tests pass, and the trajectory is valid JSON |
| `save_fault_blind_restart` | blind restart | The mutation succeeds before the first trajectory write fails; a new worker executes the same command again, receives the registered nonzero return code, and causes no second byte-tree change |
| `save_fault_reconcile` | reconcile on restart | The exact initial journal row and exact post-patch tree agree, so restart records `RECONCILED` without executing the command |
| `save_fault_reconcile_tampered` | reconcile on restart | The registered intervention changes the tree after the first worker; restart records `UNRESOLVED` without executing the command |

The snapshots have one definition across all scenarios:

- S0: before the initial worker;
- S1: after the initial worker exits;
- S2: immediately before an optional restart worker, after the registered
  intervention when applicable;
- S3: after the optional restart worker exits.

The registered fault is an application-level exception during the first
trajectory save. It occurs only after the mutation command has returned and
the out-of-workspace SQLite WAL/FULL journal has committed its initial
`EXECUTED` row. The injected trajectory contains only a registered invalid
prefix. This is not a hard crash, forced process kill, power loss, native
mini-swe-agent resume, or operating-system, SQLite, Git, or filesystem
crash-consistency experiment.

## Evidence domains and reconciliation rule

Schema v5 preserves five independent observations:

1. the registered mutation action declared in the deterministic model
   trajectory projection;
2. the return code mini-swe-agent observed;
3. the durable out-of-workspace journal decision;
4. the S0/S1/S2/S3 byte trees and Git changed paths;
5. the harness-owned test result at each snapshot.

A workspace diff and passing tests are not persisted external-effect facts.
The lane does not observe a production external system. Its narrow
`RECONCILED` decision requires both:

- exactly one registered initial journal row showing the command executed with
  the registered pre/post tree hashes; and
- the exact registered post-patch byte tree at restart.

Neither the byte tree, changed path, test result, agent output, nor trajectory
alone can produce `RECONCILED`. If journal and tree disagree, the only
registered decision is `UNRESOLVED`, with no restart command execution.

## Exact artifact

The artifact has exactly two directories (`.` and `results`) and eight regular
files:

```text
junit.xml
manifest.sha256
provenance.json
summary.json
results/clean.json
results/save_fault_blind_restart.json
results/save_fault_reconcile.json
results/save_fault_reconcile_tampered.json
```

Each result object contains only:

```text
all_registered_checks_met
fault
policy
restart
round_count
rounds
scenario_id
tamper
```

Each round contains only:

```text
all_checks_met
changed_paths
checks
journal
processes
round
scenario_id
snapshots
validations
```

Worker records expose normalized status, phase, exit code, mini-swe-agent
version, message-role sequence, model-query count, mutation declaration count,
observed return codes, and trajectory state. Journal projections expose only
the registered operation/action hashes, decision, execution flag, return code,
sequence, phase, and pre/post tree hashes. Validation records expose only
status and return code and explicitly state that output is excluded.

The artifact excludes the raw trajectory, synthetic work directory,
`.git` directory, SQLite journal and WAL/SHM files, wheel, commands, fixture
content, model messages, raw agent or shell output, exception messages,
absolute paths, environment, hostnames, process identifiers, and timestamps.

## Reproduction

CPython 3.12 is required.

Windows:

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

POSIX uses `.venv/bin/python`, `.venv/bin/effect-witness`, and `/` path
separators. Dependency, output, and optional work paths must be mutually
disjoint, start absent, and remain outside user data.

`declared_source_revision` is caller-supplied. A committed run may use a
40-character lowercase Git commit, but neither the runner nor artifact
authenticates that value.

## Offline verifier

`effect-witness verify-coding-agent`:

1. captures one bounded snapshot of the exact file and directory topology;
2. verifies complete manifest coverage and SHA-256 integrity;
3. parses strict JSON with type-sensitive equality;
4. independently recomputes all registered worker, journal, command-count,
   byte-tree, changed-path, validation, summary, provenance, and JUnit
   relationships for all 12 rounds;
5. redacts unregistered artifact paths and values from diagnostics.

The verifier imports neither the schema-v5 producer evaluator nor
mini-swe-agent. It does not execute Git, shell commands, or tests and does not
open the private journal. The manifest proves integrity relative to itself,
not publisher authenticity. Replacing the artifact and manifest requires an
external trusted Git or release digest to detect.

## Claim boundary

Schema v5 does not establish:

- mini-swe-agent native resume or crash recovery;
- exactly-once execution for arbitrary commands;
- arbitrary coding-agent correctness or model repair ability;
- SWE-bench, ProgramBench, repository, or industry performance;
- safe sandboxing or general process-tree cleanup;
- operating-system, power-loss, SQLite, Git, or filesystem crash consistency;
- production reliability, security, availability, or distributed consistency;
- Windows and Linux equivalence beyond registered observations;
- source authenticity without an external trusted Git or release digest;
- upstream adoption, endorsement, independent review, or external users;
- deployment, recruiting, or headhunter outcomes.
