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

No contributor license agreement is currently used. Contributions submitted
to this Apache-2.0 repository are handled under the terms in `LICENSE`.

Opening an issue or pull request does not imply review, acceptance, or a
service-level commitment.
