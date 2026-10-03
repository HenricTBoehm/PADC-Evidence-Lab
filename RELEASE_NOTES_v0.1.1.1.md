# PADC Evidence Lab v0.1.1.1

## Missingness Identity / Immutability Patch

This release hardens the source-completeness and provenance-binding reference
prototype without changing its core evidence-contract architecture or MCP tool
surface.

### Changes

- `MissingnessRecord` creation is idempotent: repeating an identical
  Missingness situation returns the already registered immutable record instead
  of overwriting it.
- Stable server-derived Missingness IDs now denote immutable artifact content.
- New claim identity is representation-normalized with Unicode NFC and
  whitespace collapse before hashing and new artifact storage.
- Regression tests cover exact Missingness dump stability and canonical claim
  representation identity.

### Validation

- Internal archive and SHA-256 verification: pass.
- Current build-environment validation: `compileall` pass; `pytest` 24/24 pass.
- The exact v0.1.1.1 MCP runtime smoke and wheel/sdist build remain release-host
  revalidation steps; see `VALIDATION.md` and `RELEASE_MANIFEST.json`.

### Scope

This is a **hardened reference prototype — freeze candidate**. It is not a
validated PADC implementation, a semantic evidence engine, a production
security certification, or a tamper-resistant audit ledger.
