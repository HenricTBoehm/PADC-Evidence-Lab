# Changelog

## v0.1.1.1 — Missingness Identity / Immutability Patch

- Made `MissingnessRecord` creation idempotent: an existing deterministic `missingness_id` returns the existing immutable artifact rather than overwriting `created_at`.
- Canonicalized new claim identity using Unicode NFC normalization plus whitespace collapse before hashing and new artifact storage.
- Added regression invariants for exact Missingness dump stability and canonical representation identity.
- Preserved the v0.1.1 evidence-contract architecture, MCP tool surface, extraction-surface logic, and historical provenance semantics.
- Separated current-build-environment validation from the independently reported v0.1.1 release-artifact MCP/build re-check.

## v0.1.1 — Source-Completeness and Provenance-Binding Hardened Prototype

- Added trusted `ExtractionManifest` for explicit `PAGE_INDEXED_TEXT` surface declaration.
- Stopped inferring text-surface completeness from ingested page keys.
- Bound historical NS provenance to the exact stored `review_id`.
- Added server-derived `MissingnessRecord` and exact-id binding for NE provenance.
- Rebuilt collection membership from current SourceRecords after revisions/load.
- Reworded admissible outputs as `STRUCTURALLY ADMISSIBLE PROPOSAL FOR ...`.
- Split declared semantic-query contract from actually executed review trace.
- Documented MCP-capability vs host-authority trust boundary.
- Documented audit-oriented vs tamper-resistant distinction.
- Added adversarial provenance regression tests and release/reproducibility metadata.

## v0.1.0 — Executable Architecture Probe

Initial functional implementation probe.
