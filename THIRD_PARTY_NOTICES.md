# Third-party notices

No third-party source code is vendored in this repository.

Runtime and development packages are installed from their upstream
distributions. Their licenses remain their own:

| Package | Role | Upstream license |
|---|---|---|
| [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) | Runtime protocol SDK | MIT |
| [HTTPX](https://github.com/encode/httpx) | Runtime HTTP client | BSD-3-Clause |
| [pytest](https://github.com/pytest-dev/pytest) | Tests | MIT |
| [Ruff](https://github.com/astral-sh/ruff) | Lint and format | MIT |
| [build](https://github.com/pypa/build) | Package build frontend | MIT |
| [Hatchling](https://github.com/pypa/hatch) | Package build backend | MIT |

The exact direct versions are pinned in `pyproject.toml`. Transitive dependency
resolution is not yet represented by a cross-platform hash lock; that is a
current reproducibility limitation.
