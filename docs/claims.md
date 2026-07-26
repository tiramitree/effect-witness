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

## Explicitly not established

- exactly-once execution;
- official MCP certification or conformance status;
- security;
- production reliability or availability;
- distributed consistency;
- arbitrary third-party tool correctness;
- model or agent capability;
- framework superiority;
- external users, adoption, review, reproduction, deployment, or recruiting
  outcomes.

`MATCH` means that the registered observation matched the narrow declared
effect expectation. `MISMATCH` is expected for deliberately misleading
negative controls. `NOT_APPLICABLE` means the scenario does not exercise the
relevant repeat-effect contract. None of these labels is a protocol violation
ruling.

## Evidence versus declaration

The artifact fields `model_api_calls=0` and `paid_service_calls=0` are declared
run metadata. The repository design does not contain model or paid-service
clients, but the artifact itself is not a packet-capture proof of all machine
network activity.

The manifest proves integrity relative to itself, not publisher authenticity.
Use a trusted Git commit, release digest, or other external root when
authenticity matters.
