# Python dependency security refresh

The optional coding-agent integration now pins LiteLLM 1.91.5, addressing
GHSA-3cv6-jpf6-8222. The LangGraph integration pins
langgraph-checkpoint-sqlite 3.1.1, addressing GHSA-47pj-3jcm-6whg.
Both complete constraint files retain their exact package counts and have new
SHA-256 registrations. These are version constraints, not wheel hash locks.

The runtime gates accept only the current constraint bytes and installed versions.
Offline artifact verification retains exact previous provenance registrations,
including the earlier npm registration. Schema-v4 summary dependency versions
must match the selected complete provenance registration. An old constraints
hash is not an execution allowance. Existing evidence files are unchanged.

Mini-swe-agent remains 2.4.6. Its existing wheel provenance and selected runtime
file hashes remain unchanged because this refresh changes its LiteLLM dependency,
not that wheel. No model or paid service call is required for verification.

The replacement wheels were downloaded from files.pythonhosted.org and checked
against the SHA-256 values in their official PyPI version metadata:

| Wheel | SHA-256 |
| --- | --- |
| `litellm-1.91.5-py3-none-any.whl` | `db09c6ea0b7c7de034b6c8b628208b000b54e02ef557468f84c2e63fbd7c8560` |
| `langgraph_checkpoint_sqlite-3.1.1-py3-none-any.whl` | `8505c54c94a658080525d7e6780fdd4e0c078ff2566b30d399c02cc9f9af1c63` |

Each wheel's active direct requirements are compatible with the corresponding
registered constraint file. This check covers the two changed wheels; it is not
a new wheel hash lock for the complete environment.
