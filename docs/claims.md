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
CI boundary above. The schema-v3 artifact is generated ephemerally rather than
committed as reference evidence.

## Explicitly not established

- Runtime integrity of the complete transitive `node_modules` tree.

- exactly-once execution;
- official MCP certification or conformance status;
- security;
- production reliability or availability;
- distributed consistency;
- arbitrary third-party tool correctness;
- package-wide correctness for the filesystem server;
- production filesystem behavior, permissions, timestamps, links, or
  concurrent mutation behavior;
- a verified rebuild from the npm registry metadata `gitHead`;
- model or agent capability;
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
