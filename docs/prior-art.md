# Related work and bounded differentiation

Snapshot date: 2026-07-27.

This comparison frames scope. It is not a claim that EffectWitness is the
first, only, or generally superior implementation.

| Work | Relevant scope | EffectWitness boundary |
|---|---|---|
| [MCP tool annotations](https://blog.modelcontextprotocol.io/posts/2026-03-16-tool-annotations/) | Official explanation of effect-related tool hints and their untrusted nature | Treats annotations as declarations to compare, never enforcement or certification |
| [Official filesystem server](https://www.npmjs.com/package/@modelcontextprotocol/server-filesystem) | Reference MCP filesystem implementation | Schema v3 executes only exact version 2026.7.10 on five registered repeated inputs; it makes no package-wide verdict |
| [MCP conformance](https://github.com/modelcontextprotocol/conformance) | Official protocol conformance scenarios | Does not replace or claim a result from the official framework |
| [MCP Tasks](https://modelcontextprotocol.io/specification/2025-11-25/basic/utilities/tasks) | Task-augmented request lifecycle | Current v0 does not claim task-level idempotency |
| [Atomix](https://github.com/mpi-dsg/atomix) and its [paper](https://arxiv.org/abs/2602.14849) | Transactions, recovery, compensation, idempotency, replay, and crash windows for agentic workflows | EffectWitness is an observation workbench, not a transaction runtime |
| [Replaysafe](https://github.com/JobGuards/Replaysafe) | Side-effect control plane, reconciliation, compensation, and adapters | No runtime guard or framework adapter is claimed |
| [OnceOnly](https://www.onceonly.tech/) | Hosted idempotency and execution policy | No hosted service is provided |
| [AgentCheck](https://github.com/aritra741/AgentCheck) and its [paper](https://arxiv.org/abs/2607.11098) | MCP response-fault testing | Current focus is declaration/client/durable-effect separation in a controlled fixture |
| [A2A TCK](https://github.com/a2aproject/a2a-tck) and [A2A specification](https://github.com/a2aproject/A2A/blob/main/docs/specification.md) | A2A transport compatibility and optional Send Message idempotency | A2A is a possible future adapter, not part of v0 evidence |

## Dated repository snapshots used during design

The local design audit inspected these upstream revisions without copying
their source:

- Atomix: `61e411be662bb021634f0e84bc184bf6074905b4`
- MCP conformance: `a865118206d4d8cc8dbc5f5201607839281d0c3b`
- A2A TCK: `5996b79f9cefa6fc390980e383e358a66fb9e49e`
- AgentCheck: `2b89d2c5782ff81d20843391e1bd410d3e7ffbe9`
- Official filesystem-server npm metadata reports:
  `9a96ea6e5913736f92b88345bf51caeaaa8e719f`

Those revisions are a dated snapshot, not a claim about later upstream state.
The npm `gitHead` is a registry-metadata report, not a verified source rebuild
binding. No third-party source file is included in this repository.

## Current narrow hypothesis

A useful protocol-effect workbench should preserve three independently
auditable views:

1. the effect contract a protocol descriptor declares;
2. the outcome a client could observe and the policy it chose;
3. the durable effect cardinality a controlled witness records.

The v0 repository tests whether that separation yields reproducible,
machine-verifiable evidence in a deliberately small MCP fixture. Broader
novelty, usefulness, or adoption remains unproven.
