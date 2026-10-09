# Filesystem dependency security refresh

The current filesystem lane uses the official server 2026.7.10 with JavaScript
MCP SDK 1.32.1 and refreshed compatible transitive dependencies. Runtime setup
accepts only the current tracked package lock and its registered hash.

Offline schema-v3 and schema-v4 verification also recognizes the exact earlier
lock hash paired with SDK 1.29.0 so already published evidence remains
verifiable. That historical binding is not an approved runtime dependency
closure and does not assert that the old dependencies are free of
vulnerabilities. The old evidence files are unchanged. Mixing an earlier lock
hash with the current SDK, or supplying an unregistered hash, is rejected.
