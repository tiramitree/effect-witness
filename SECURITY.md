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

Dependency preparation performs an npm registry download into a fresh ignored
directory using the tracked lock and `--ignore-scripts`. Inspect dependency and
license changes before altering the lock. Never add credentials to npm
configuration for this workflow.

If you find a security-relevant problem, open a GitHub issue containing the
smallest safe reproduction. Do not include credentials, personal information,
private hostnames, private paths, or production data. There is currently no
private disclosure email or paid support channel.

No response-time or remediation-time commitment is made.
