# Contributing

Small, evidence-backed changes are welcome through GitHub Issues and pull
requests.

Before proposing a change:

1. keep the fixture loopback-only and synthetic;
2. add a failing regression for behavior changes;
3. run `python -m pytest`, `python -m ruff check --no-cache src tests scripts`,
   `python -m ruff format --check --no-cache src tests scripts`, and
   `python scripts/privacy_scan.py .`;
4. update the claim boundary when evidence scope changes;
5. do not include personal data, private infrastructure details, credentials,
   copied proprietary code, or unverifiable performance claims.

For packaging or real-filesystem changes, also run:

```text
python -m build
python scripts/verify_distribution_boundary.py dist
python scripts/prepare_filesystem_server.py --output-dir <fresh-temp-dir>
effect-witness run-filesystem --output-dir <fresh-artifact-dir> --dependency-dir <fresh-temp-dir>
effect-witness verify-filesystem --artifact-dir <fresh-artifact-dir>
python scripts/privacy_scan.py <fresh-artifact-dir>
```

Keep the npm dependency tree outside the repository. Do not commit or package
`node_modules`, npm tarballs, Node runtimes, generated server logs, or
schema-v3 artifacts. Changes to the tracked npm package/lock pair must update
the exact dependency registration, installed-file allowlist, tests,
third-party notices, and claim boundary together. Dependency preparation must
remain lockfile-only and lifecycle-script-free.

No contributor license agreement is currently used. Contributions submitted
to this Apache-2.0 repository are handled under the terms in `LICENSE`.

Opening an issue or pull request does not imply review, acceptance, or a
service-level commitment.
