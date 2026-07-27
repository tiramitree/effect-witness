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
`1.29.0`, whose
package metadata reports MIT and SRI:

`sha512-zo37mZA9hJWpULgkRpowewez1y6ML5GsXJPY8FI0tBBCd77HEvza4jDqRKOXgHNn867PVGCyTdzqpz0izu5ZjQ==`

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
