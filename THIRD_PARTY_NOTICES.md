# Third-party notices

Original EffectWitness code is licensed under the repository's Apache-2.0
`LICENSE`. Third-party packages retain their own terms. This file reports
bounded dependency and packaging facts; it is not a complete legal analysis.

No third-party source, npm tarball, `node_modules` tree, or Node runtime is
distributed in the EffectWitness Python wheel. The source distribution carries
the tracked npm package/lock metadata needed to prepare the optional
real-filesystem lane, but not the installed npm packages. Preparation downloads
the dependencies resolved by the tracked lock from the npm registry into a
local ignored directory.

## Exact filesystem-lane npm facts

The registered external server is
`@modelcontextprotocol/server-filesystem` version `2026.7.10`.

- npm tarball:
  `server-filesystem-2026.7.10.tgz`
- bytes: `17835`
- SHA-256:
  `c17c1da371c8089cff2206cce3001194d8276bae2b5ac1e2b425b6612068e3ba`
- npm SHA-1: `b19597401bfbf055662eb9bc9bd92f13ecaf5661`
- npm SRI:
  `sha512-Mmjg4anFBD5OzbPnGJOA0jPPN8645ERhQk38HQLpSenx1ox9bfdPkmAzUnNjeQtqQGFLtKe13J20RtLBmUKMZA==`
- unpacked size/file count: `69088` bytes and 7 files

The exact package's `package.json` license field says
`SEE LICENSE IN LICENSE`, while the exact seven-file npm tarball contains no
`LICENSE` file. This is a verifiable packaging fact and omission; no legal,
security, or nonconformance conclusion is drawn from it.

The npm registry metadata reports `gitHead`
`9a96ea6e5913736f92b88345bf51caeaaa8e719f`. EffectWitness does not claim that
the npm package was independently rebuilt from or proven identical to that
source commit.

At that reported commit, the upstream repository's root `LICENSE` is 12,227
bytes with SHA-256
`0382b0057770ca05e9c350a50aa3b1c1fea84da0bc81d723bf00b9aa841be58a`.
Its text describes an MIT-to-Apache-2.0 transition, retains MIT treatment for
contributions whose authors did not consent to relicensing, and assigns
CC-BY-4.0 to non-specification documentation. Those mixed terms must not be
simplified to one blanket MIT or Apache-2.0 label for the exact package.

The tracked npm lock also resolves `@modelcontextprotocol/sdk` version
`1.32.1`, whose
package metadata reports MIT and SRI:

`sha512-2DdE+SJDtzLEEWzY1ZjY7Q+VcPhcV1KisD3zI4u0XZyktsjHum1mwbMI+JaulUBi2OZk+KJAi2uPXzxichPkdw==`

The tracked lock and registered hashes provide a technical dependency boundary.
They do not replace review of all applicable dependency notices or terms.
Before execution, EffectWitness rechecks the tracked lock bytes and the exact
seven-file server distribution. It does not rehash every installed transitive
`node_modules` file and therefore does not establish integrity of the complete
runtime dependency tree.
One non-resolution deprecation-message contact field was removed from the
tracked lock to avoid redistributing an unrelated personal contact. Package
versions, resolved URLs, integrity fields, and dependency relationships were
not changed by that redaction.

## Python runtime and development packages

Runtime and development packages are installed from their upstream
distributions:

| Package | Registered role/version | Upstream license field |
|---|---|---|
| [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) | Runtime protocol SDK 1.28.1 | MIT |
| [HTTPX](https://github.com/encode/httpx) | Runtime HTTP client 0.28.1 | BSD-3-Clause |
| [pytest](https://github.com/pytest-dev/pytest) | Tests 9.1.1 | MIT |
| [Ruff](https://github.com/astral-sh/ruff) | Lint and format 0.16.0 | MIT |
| [build](https://github.com/pypa/build) | Package build frontend 1.5.0 | MIT |
| [Hatchling](https://github.com/pypa/hatch) | Package build backend 1.31.0 | MIT |

The exact direct versions are pinned in `pyproject.toml`. Python transitive
dependency resolution is not represented by a cross-platform hash lock; that
remains a reproducibility and notice-completeness limitation.

## Optional LangGraph replay integration

The schema-v4 replay lane is installed only through the
`langgraph-replay` extra. EffectWitness wheels and source distributions do not
bundle these packages, their native libraries, or their source code. The source
distribution carries a 58-package version constraint snapshot, not a
cross-platform hash lock.

| Package | Registered role/version | Upstream license field |
|---|---|---|
| [LangGraph](https://github.com/langchain-ai/langgraph) | Workflow runtime 1.2.9 | MIT |
| [LangGraph Checkpoint](https://github.com/langchain-ai/langgraph) | Checkpoint interface 4.1.1 | MIT |
| [LangGraph SQLite Checkpoint](https://github.com/langchain-ai/langgraph) | SQLite saver 3.1.0 | MIT |
| [sqlite-vec](https://pypi.org/project/sqlite-vec/) | Required native transitive dependency 0.1.9 | `MIT License, Apache License, Version 2.0` |
| [orjson](https://github.com/ijl/orjson) | Transitive serialization dependency 3.11.9 | `MPL-2.0 AND (Apache-2.0 OR MIT)` |
| [Requests](https://github.com/psf/requests) | Transitive HTTP dependency 2.34.2 | Apache-2.0 |

The exact `sqlite-vec` 0.1.9 wheel metadata uses the quoted non-SPDX license
string and its inspected Windows wheel contains no license file. It publishes
native wheels for a bounded platform set and no source distribution; the
registered Windows amd64 and manylinux x86_64 wheels are therefore an
installation boundary, not a portability claim.

The inspected Requests 2.34.2 wheel contains a `NOTICE` file with SHA-256
`f5110972dedad2b4e9d314518daf3b7d72d6e02e499acd802181de6f74571dcc`.
Because EffectWitness does not redistribute Requests, that notice is not copied
into the EffectWitness wheel. Any future bundled environment, container, or
offline dependency archive must preserve the applicable upstream license and
notice files and must stop if the missing `sqlite-vec` license text remains
unresolved.

## Optional mini-swe-agent coding integration

Schema v5 declares optional dependencies through the `coding-agent` extra. Its
registered reproduction path installs the exact prepared wheel directly under
the constraint snapshot. The preparer downloads, verifies, and keeps outside
this repository the exact public PyPI wheel
`mini_swe_agent-2.4.6-py3-none-any.whl` (115,037 bytes; SHA-256
`a35463c553ac825c7773b03cfa69cd44958e3af20155dcc5711fdf9e4c67cd54`).
The wheel, its source code, and its installed files are not bundled in an
EffectWitness wheel, source distribution, or schema-v5 evidence artifact.

The exact wheel's PyPI metadata reports mini-swe-agent 2.4.6 as MIT licensed,
with Python requirement `>=3.10` and an Alpha development-status classifier.
That upstream metadata is an attribution and dependency fact, not a claim that
the lane supports every upstream-compatible interpreter or platform. Schema v5
supports only CPython 3.12 on x86-64 Windows or Linux.

The schema-v5 source distribution carries a 93-version CPython 3.12 constraint
snapshot with SHA-256
`a2a4b3cf0af75c357e1e4578d0cc4b0ffa222dcb9358a0b60a4e3a47512196eb`.
It is a version registration, not a cross-platform wheel hash lock or a
complete transitive-dependency notice inventory. A future bundle or
redistribution of mini-swe-agent must preserve the applicable upstream MIT
license and notices and receive a fresh dependency and license review.
