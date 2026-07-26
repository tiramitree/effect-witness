# Evidence schema v2

Schema v2 supersedes unpublished local schema-v1 candidates. It is intentionally
strict: the verifier recognizes the exact ten registered scenarios.

## Directory shape

```text
artifact/
  manifest.sha256
  summary.json
  junit.xml
  results/
    <scenario_id>.json
```

Every file except `manifest.sha256` must appear exactly once in the manifest.
Paths are relative POSIX paths. Absolute paths, `..`, backslashes, links,
junctions, non-regular entries, oversized entries, missing entries, and
unmanifested files are rejected.

The verifier captures each accepted file once into a bounded byte snapshot,
checks its identity and version around that read, and uses only those bytes for
hashing and semantic verification. JSON is parsed strictly: duplicate keys,
non-standard constants, non-finite values, unregistered fields, and
type-substituted values are rejected.

## Result domains

Each result contains:

- protocol declaration: annotations and input schema;
- stimulus: call count, fault, policy, and every write-attempt argument hash;
- observations: transport completion, MCP error status, normalized exception
  types, and response;
- client journal: canonical request/response hashes and decisions;
- intermediate witness when a before-retry fact is required;
- concurrency witness for the two barrier-synchronized eight-call scenarios;
- final witness: attempt states, server fault modes, effect cardinality, and
  payload hashes;
- registered expected label and evidence checks.

## Registered matrix

| Category | Scenarios | Expected result |
|---|---:|---|
| Truthful repeated idempotent writes | 3 | `MATCH` |
| Deliberately misleading idempotent/read-only controls | 4 | `MISMATCH` |
| Single ambiguous call or confirmed pre-commit absence | 3 | `NOT_APPLICABLE` |

An expected `MISMATCH` is a passing negative control, not a JUnit failure.

## Verification scope

The verifier recomputes the registered matrix and cross-checks the client
journal state machine, decisions, responses, complete registered annotations,
exact registered input schemas and argument hashes, reconciliation facts,
the synchronized concurrency witness, fault modes, attempt states, effect
counts, JUnit, summary, and manifest.

It does not rerun the scenarios. It does not prove that the publisher is
authentic, that the host made no other network calls, or that an external
system would behave the same way.
