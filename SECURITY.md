# Security policy

EffectWitness is a pre-alpha testing fixture, not a security product.

The fixture contains deliberate process-exit and response-delay controls. It
has no authentication and is forcibly restricted to `127.0.0.1`. Do not expose
it through a proxy, tunnel, container port mapping, or public interface. Do not
point it at production data.

If you find a security-relevant problem, open a GitHub issue containing the
smallest safe reproduction. Do not include credentials, personal information,
private hostnames, private paths, or production data. There is currently no
private disclosure email or paid support channel.

No response-time or remediation-time commitment is made.
