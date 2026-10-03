# Architecture Notes — v0.1.1.1

## Governing separation

The prototype implements four separate layers:

1. **Trusted source state**
   - source artifact hash (optional)
   - page-indexed extracted text
   - immutable source revision
   - `ExtractionManifest` for the declared `PAGE_INDEXED_TEXT` surface
   - current collection membership

2. **Server-derived provenance artifacts**
   - `EvidenceObject`
   - `DocumentReview`
   - `MissingnessRecord`

3. **Agent proposal**
   - claim
   - proposed epistemic status
   - references to server-created evidence IDs
   - conditions for partial support
   - optional model-reported confidence

4. **Deterministic structural admissibility**
   - guards test whether the proposal has the required server-established artifacts
   - every assessment attempt is persisted

Semantic truth is not decided by the guard engine.

## Common provenance rule

v0.1.1 hardens three previously independent-looking failure modes under one rule:

> **Derived state must not acquire authority independent of the authoritative state from which it
> was derived.**

Consequences:

- ingested page keys do not define the expected document surface;
- an arbitrary current review does not replace the exact review bound to a historical NS assessment;
- a persisted collection index does not override membership declared by current SourceRecords;
- a later MissingnessRecord does not replace the exact missingness artifact bound to historical NE.

## Text-surface completeness

The `ExtractionManifest` declares an evaluated surface, currently only:

```text
PAGE_INDEXED_TEXT
```

`declared_text_surface_complete = true` requires a trusted expected page surface and a matching
extracted page surface. It is intentionally narrower than document completeness. Excluded
modalities remain explicit.

```text
declared_text_surface_complete
    != document_semantically_exhausted
```

A `DocumentReview` can be `protocol_complete` only when it traverses the entire declared complete
text surface.

## Review contract vs execution trace

`DocumentReview` records two separate hashes:

```text
H_C = review_contract_hash
H_E = executed_review_trace_hash
```

Declared semantic queries belong to `H_C`. In v0.1.1.1 they are not executed, and `H_E` records:

```text
semantic_search_executed = false
semantic_search_adapter  = null
```

This prevents declaration from being mistaken for execution.

## Stable ID means immutable artifact content

v0.1.1.1 adds one patch-level invariant for newly created Missingness artifacts:

```text
MIS_1 = MIS_2  =>  dump(MIS_1) = dump(MIS_2)
```

`create_missingness_record()` computes the deterministic ID first and returns an existing registry
record unchanged when that ID is already present. It must not overwrite the artifact with a new
timestamp. New claim identity is canonicalized using Unicode NFC plus whitespace collapse before
hashing/storage. This is representation normalization only; it does not assert semantic equivalence.

## Historical identity vs current provenance

For S/P/C, provenance is tied to exact `EvidenceObject` IDs.

For NS:

```text
ProvValid(assessment_NS)
    iff the review_id bound to that assessment is still current and valid
```

For NE:

```text
ProvValid(assessment_NE)
    iff the missingness_id bound to that assessment is still current and valid
```

A newer artifact cannot substitute for an older bound artifact.

```text
historical structurally_admissible = immutable assessment fact
current provenance_valid           = revision-relative recomputation
```

## Collection membership

The collection index is derived from current `SourceRecord.collection_ids`. It is rebuilt after
source revision and after state load. Serialized collection data is non-authoritative.

## Important non-collapse relations

```text
Model confidence               != evidence status
Evidence existence             != semantic support
Historical admissibility       != current provenance validity
Ingested pages                 != expected document surface
Complete PAGE_INDEXED_TEXT     != semantic document exhaustion
Declared semantic query        != executed semantic search
Structurally admissible NS      != adjudicated NS
Agent proposal                  != server fact
MCP capability boundary        != host authority boundary
Persistent audit log           != tamper-resistant ledger
```

## Trust boundary

Not exposed through MCP:

- source ingestion
- source revision assignment
- expected-surface declaration
- page numbering
- source and manifest hashes
- MissingnessRecord creation as a direct agent action
- document-review completion declaration

Exposed through MCP:

- source listing
- server-side evidence search
- server-side review execution
- assessment proposal/validation
- collection-scoped matrix generation

No MCP tool exposes trusted ingestion. Protection against direct state-file modification
additionally depends on host-level authority separation.

## Current limitations

`run_document_review` is a deterministic page-indexed-text traversal and lexical-search protocol.
It does not execute semantic search and does not claim semantic exhaustiveness. `NS` therefore
means that an NS proposal is structurally admissible under the declared completed text-review
protocol; it does not prove a universal absence of support.

The persistent audit state is audit-oriented, not cryptographically append-only or tamper-resistant.
