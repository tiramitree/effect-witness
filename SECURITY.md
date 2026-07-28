# Security policy

EffectWitness is a pre-alpha testing fixture, not a security product.

The fixture contains deliberate process-exit and response-delay controls. It
has no authentication and is forcibly restricted to `127.0.0.1`. Do not expose
it through a proxy, tunnel, container port mapping, or public interface. Do not
point it at production data.

The real-filesystem lane launches an exact external server over local stdio
against a newly created temporary sandbox. Do not point its server argument or
`--work-dir` at user data, source repositories, shared storage, production
paths, or a symlink/junction/reparse tree. Preserve the minimal child
environment, null stderr sink, exact dependency-file checks, and relative
byte-tree boundary. The lane does not establish sandbox security or make the
external server safe for untrusted inputs.

The replay lane creates checkpoint and event-journal SQLite files only inside
a newly owned disposable work directory and launches registered fault and
resume workers in separate process groups. Never point `--work-dir`, the
filesystem dependency, output, or any sandbox path at user data, a repository,
shared storage, or production state. These paths must not overlap. The lane is
not a crash-safety or recovery product.

Dependency preparation performs an npm registry download into a fresh ignored
directory using the tracked lock and `--ignore-scripts`. Inspect dependency and
license changes before altering the lock. Never add credentials to npm
configuration for this workflow.

The replay Python constraints are an exact version snapshot, not a
cross-platform wheel hash lock. Do not add package-index credentials to this
workflow. Changes to native or transitive dependencies require a new
platform/license review before the registered versions or architectures are
expanded.

The schema-v5 coding-agent lane launches mini-swe-agent 2.4.6
`LocalEnvironment`, which executes a real shell command inside a newly owned
synthetic Git workspace. The exact-command adapter, restricted worker
environment, process group, timeout, output bound, disjoint paths, and
owned-root cleanup reduce accidental exposure; they are not a security
sandbox. Never point `--work-dir`, the dependency directory, output directory,
workspace, or Git command at user data, an existing repository, shared
storage, credentials, or production state.

The schema-v5 fault is an application-level first trajectory-write exception
after the registered mutation and journal write. Do not describe it as a hard
crash, power-loss test, native mini-swe-agent resume, or SQLite/filesystem
crash-consistency result. A Git diff or passing validation is not a persisted
external-effect fact. Reconciliation is limited to agreement between the exact
out-of-workspace WAL/FULL journal row and exact registered workspace
postcondition.

The coding-agent dependency preparer downloads one exact public wheel without
environment proxies and verifies its filename, 115,037-byte size, and SHA-256
`a35463c553ac825c7773b03cfa69cd44958e3af20155dcc5711fdf9e4c67cd54`.
Do not add package-index credentials, alternate indexes, or authentication to
this workflow. The 93-version CPython 3.12 constraint snapshot is not a
cross-platform hash lock; any dependency, wheel, runtime-file, platform, or
license change requires renewed registration and review.

Do not retain or publish schema-v5 raw trajectories, work roots, `.git`
directories, journal databases or WAL/SHM files, upstream wheels, command text,
model messages, raw shell or agent output, environment values, absolute paths,
hostnames, process identifiers, timestamps, or exception messages. The public
artifact carries normalized hashes and bounded facts only.

If you find a security-relevant problem, open a GitHub issue containing the
smallest safe reproduction. Do not include credentials, personal information,
private hostnames, private paths, or production data. There is currently no
private disclosure email or paid support channel.

No response-time or remediation-time commitment is made.
