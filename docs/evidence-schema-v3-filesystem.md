# Schema v3: exact filesystem-server lane

Schema v3 is reserved for the bounded real-implementation lane. It is not an
extension of schema v2 and is verified by `effect-witness verify-filesystem`.
The schema-v2 verifier and bundled v0.1 reference remain supported unchanged.
Schema v4 is a separate replay artifact and verifier; its S0/S1/S2/S3 states
do not reinterpret schema-v3 S0/S1/S2 evidence.

## Registered execution

The execution registration is:

- MCP Python SDK 1.28.1 over stdio;
- Node 24.18.0;
- `@modelcontextprotocol/server-filesystem` version `2026.7.10`;
- JavaScript MCP SDK 1.29.0 through the tracked npm lock;
- protocol version `2025-11-25`;
- server identity `secure-filesystem-server` version `0.2.0`;
- Windows and Linux only.

Each scenario is initialized in an isolated temporary directory. `S0` is
captured before the first call, `S1` after the first call, and `S2` after the
second call. The registered scenarios are:

| Scenario | Tool | Registered relative input | Narrow observation |
|---|---|---|---|
| `read_text_file` | `read_text_file` | `fixture.txt` | both reads return the registered byte length/hash; S0=S1=S2 |
| `create_directory` | `create_directory` | `new-dir` | first call creates one directory; repeat adds no visible effect |
| `create_directory_nested_claim` | `create_directory` | `parent/child` | Windows: two MCP errors and no visible effect; Linux: that result or exact nested creation with no repeat effect |
| `write_file` | `write_file` | `document.txt` | first call creates the registered byte length/hash; repeat adds no visible effect |
| `edit_file` | `edit_file` | `document.txt`, one registered replacement | first call changes the registered hash; repeat returns an MCP error and adds no visible effect |

These are observations for exact inputs and versions. The nested-create result
is not a bug, security, or protocol-conformance claim.

## Exact artifact inventory

The output has ten regular files:

```text
junit.xml
manifest.sha256
provenance.json
summary.json
tools.json
results/create_directory.json
results/create_directory_nested_claim.json
results/edit_file.json
results/read_text_file.json
results/write_file.json
```

`manifest.sha256` covers every other file and never itself. The artifact root,
all files, and all directories must be ordinary and unchanged during one
bounded snapshot. Extra or missing files fail verification.

The requested output must be absent. Execution writes to an ordinary
same-parent staging directory, removes its exact temporary work root, writes
the complete manifest from fail-closed file reads, then atomically renames the
staging directory to the requested output. A failed execution does not publish
a partial output as a sealed artifact.

## Result records

Each result has this exact top-level field set:

```text
checks
expectation_met
first_call
observation_outcome
s0
s0_equals_s1
s1
s1_equals_s2
s2
scenario_id
second_call
stimulus
stimulus_sha256
tool_name
```

The public `stimulus` uses only relative paths, byte lengths, counts, and
SHA-256 values. The absolute path sent to the server exists only in process
memory and is not hashed into evidence.

Each call record contains completion, MCP `isError`, content-type/count, and
structured-content-presence facts. Raw text is never included. The read
scenario records only the returned byte length and SHA-256. Every mutating
scenario records `response_text_redacted=true`.

A byte tree contains sorted unique entries plus the canonical SHA-256 of that
entry array:

```json
{
  "entries": [
    {"kind": "directory", "path": "relative/directory"},
    {
      "bytes": 12,
      "kind": "file",
      "path": "relative/file.txt",
      "sha256": "64 lowercase hexadecimal characters"
    }
  ],
  "tree_sha256": "64 lowercase hexadecimal characters"
}
```

Paths reject absolute syntax, backslashes, drive/colon syntax, empty, `.`, and
`..` segments, and control characters. Capture rejects symlinks, junctions or
reparse points, non-regular files, oversized files, and files that change
identity, size, or relevant version metadata while read.

## Descriptor and provenance records

`tools.json` binds each registered tool name to:

- the complete observed annotation object;
- the SHA-256 of the description, without retaining its text;
- the SHA-256 of the remaining descriptor, without retaining that descriptor;
- one registered Boolean for the nested-directory description claim.

`provenance.json` binds the tracked lock hash, exact package identities and
integrities, the exact seven installed server files by size and SHA-256, the
Python SDK version, and a bounded upstream-license record. The npm
`gitHead` value is explicitly an npm registry-metadata report, not proof of a
source rebuild. The npm package and installed `node_modules` are not copied
into the artifact. The launch-time check does not rehash every installed
transitive file, so this provenance does not establish integrity of the
complete `node_modules` tree.

`summary.json` binds the lane, schema version, runtime versions and operating
system, protocol/server identity, scenario count and outcome counts, evidence
boundary, blocked claims, and source revision.

## Privacy and claim boundary

The registered evidence boundary requires all of these to be absent:

- absolute paths;
- environment values;
- generated fixture content;
- hostnames and ports;
- raw mutating-tool responses;
- raw server logs;
- raw tool-result text.

This schema does not establish authenticity, official MCP conformance,
package-wide correctness, production filesystem behavior, link/permission/
timestamp behavior, concurrency behavior, security, or external adoption.
Manifest closure provides integrity only relative to itself; a trusted commit
or release digest is still required for publisher authenticity.
