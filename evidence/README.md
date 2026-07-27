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

No schema-v3 real-filesystem artifact is bundled. That lane depends on an
external exact npm closure and records an operating-system-bound observation;
CI generates, verifies, and privacy-scans a fresh artifact on Windows and
Ubuntu without uploading it. Its format and reproduction commands are
documented in
[`docs/evidence-schema-v3-filesystem.md`](../docs/evidence-schema-v3-filesystem.md).
