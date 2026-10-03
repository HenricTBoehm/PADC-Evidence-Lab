# PADC Evidence Lab v0.1.1.1

**Source-Completeness and Provenance-Binding Hardened Prototype**

Author: Henric T. Böhm — ORCID: 0009-0005-0349-6341

Prototype implementation of an audit-oriented evidence contract for agentic research workflows.

The core separation is:

**Proposal != Evidence != Admissibility != Adjudication**

The MCP agent may propose an epistemic status, but it cannot directly create source facts,
page locators, extraction-completeness facts, provenance records, missingness records, or guard
outcomes.

## Research question and patch status

v0.1.0 asked whether the separation could be implemented. v0.1.1 asks a narrower adversarial
question:

> **Does the implemented separation survive provenance counterexamples involving source
> completeness, historical artifact binding, and derived-state authority?**

v0.1.1.1 is a narrowly scoped identity/immutability patch. It preserves the v0.1.1 architecture
and adds the invariant that a stable server-derived artifact ID denotes immutable artifact content.
Repeated creation of the same Missingness situation returns the already registered record. New
claims are representation-normalized (Unicode NFC plus whitespace collapse) before claim hashing
and new artifact storage; this normalizes representation, not meaning.

The target status is **HARDENED REFERENCE PROTOTYPE — FREEZE CANDIDATE**, not a validated
PADC implementation, semantic evidence engine, or production audit system.

## Epistemic statuses

- `S` — Supported
- `P` — Partially Supported
- `NS` — Not Supported
- `C` — Contradicted
- `NE` — Non-Evaluable

`S`, `P`, and `C` require current server-generated `EvidenceObject` IDs. `P` additionally
requires explicit conditions.

`NS` requires a current, claim-specific, protocol-complete `DocumentReview` over an explicitly
declared complete `PAGE_INDEXED_TEXT` surface. The assessment binds to the exact `review_id`.
A later review cannot retroactively revalidate an older NS assessment.

`NE` requires a server-generated `MissingnessRecord`. The assessment binds to the exact
`missingness_id`. A later MissingnessRecord cannot retroactively revalidate an older NE
assessment.

Passing a guard means only:

> **STRUCTURALLY ADMISSIBLE PROPOSAL FOR `<status>`**

It does not mean that the status has been semantically adjudicated.

## Declared extraction surface

v0.1.1.1 does **not** infer document completeness from the set of pages that happened to be
ingested. Trusted ingestion must declare the expected `PAGE_INDEXED_TEXT` surface using either
`--expected-page-count` or `--expected-pages`.

The resulting `ExtractionManifest` records, among other fields:

- `surface_type = PAGE_INDEXED_TEXT`
- expected and extracted page numbers
- missing and unexpected page numbers
- `extraction_complete`
- `declared_text_surface_complete`
- excluded modalities
- extraction method and version
- `extraction_manifest_hash`

A complete page-indexed text surface does **not** imply semantic exhaustion of the complete
document. By default, the declared text surface explicitly excludes `IMAGES`, `TABLE_STRUCTURE`,
and `EMBEDDED_FILES`.

Therefore:

```text
protocol_complete_text != document_semantically_exhausted
```

## Trust boundary

Trusted source ingestion is intentionally **not exposed as an MCP tool**.

A source is ingested out-of-band through `padc-evidence-ingest`. The MCP server can search and
reference trusted state but no MCP tool exposes trusted ingestion.

**This is an MCP capability boundary, not a complete operating-system security boundary.**
Protection against direct modification of the JSON state file additionally depends on host-level
authority separation. If an agent has a separate shell or filesystem capability with write access
to that state file, the MCP boundary alone does not prevent such modification.

The persistent audit log is **audit-oriented**. It is not append-only by cryptographic enforcement,
externally attested, or tamper-resistant.

## Install

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -c constraints.txt -e ".[dev]"
```

The reference constraints pin MCP 2.3.0 and the dependency versions used for the v0.1.1/v0.1.1.1
core regression runs. See `VALIDATION.md`. The trusted page-extraction subprotocol remains version
`0.1.1` because v0.1.1.1 does not change extraction semantics; it patches claim representation
normalization and Missingness artifact identity.

## Trusted ingestion

Prepare page-indexed text:

```json
{
  "1": "First page text...",
  "2": "Second page text..."
}
```

The bundled example intentionally uses the page labels `1` and `12`. If those are the
trusted expected page labels for the declared text surface, ingest it as:

```bash
padc-evidence-ingest \
  --state ./data/evidence_state.json \
  --item-id DOC_001 \
  --title "Example Paper" \
  --pages-json ./examples/doc_001_pages.json \
  --collection COLL_MAIN \
  --expected-pages 1,12
```

For an ordinary contiguous twelve-page document, use `--expected-page-count 12`. If only pages
1 and 12 were then ingested, pages 2--11 would be recorded as missing and the declared text
surface would remain incomplete.

If neither expected-page option is supplied, the ingested pages remain searchable, but
`declared_text_surface_complete` is false and a complete NS review cannot be established.

Optionally add `--artifact path/to/original.pdf` to record the SHA-256 of the original artifact.
Re-ingesting the same `item_id` creates a new immutable source revision. Historical assessment
identity remains unchanged; current provenance may become invalid.

## MCP tools

The MCP tool surface remains deliberately small:

- `list_sources()`
- `find_evidence(item_id, query, limit=5)`
- `run_document_review(item_id, claim, search_terms=[], semantic_queries=[])`
- `validate_evidence_assessment(proposal)`
- `build_evidence_matrix(collection_id)`

There is deliberately no MCP tool for registering source text, assigning source revisions,
creating MissingnessRecords directly, or declaring a review complete.

## Semantic queries

The current review API retains `semantic_queries` as a declaration field for forward-compatible
experiments, but **no semantic-search adapter is executed in v0.1.1.1**. Reviews record this as:

```text
declared_semantic_queries_not_executed = [...]
semantic_search_executed = false
semantic_search_adapter = null
```

Two hashes separate contract from execution:

```text
review_contract_hash        = hash(declared review contract)
executed_review_trace_hash  = hash(actually executed review trace)
```

Unexecuted semantic queries may affect the contract hash; they never masquerade as executed
search in the execution trace.

## Artifact identity and Missingness idempotence

For new server-derived Missingness artifacts, identity is content-stable:

```text
MIS_1 = MIS_2  =>  dump(MIS_1) = dump(MIS_2)
```

After the deterministic `missingness_id` is computed, an existing record under that ID is returned
unchanged rather than overwritten with a new `created_at`. New claim identity uses Unicode NFC
normalization and collapses whitespace runs before hashing/storage. This prevents representational
variants such as repeated spaces or canonically equivalent Unicode forms from creating or
overwriting semantically intended duplicate Missingness artifacts. No semantic equivalence beyond
this representation normalization is inferred.

## Audit semantics

`structurally_admissible` is historical: it records whether the proposal passed the guards at
submission time.

`provenance_valid` is revision-relative: it is re-computed against the current trusted source
state **using the exact supporting artifact IDs originally bound to the assessment**.

Thus:

```text
Assessment identity is historical.
Provenance validity is revision-relative.
```

and a valid matrix state may be:

```text
structurally_admissible = true
provenance_valid        = false
```

A later `DocumentReview` cannot replace the `review_id` bound to an older NS assessment. A later
`MissingnessRecord` cannot replace the `missingness_id` bound to an older NE assessment.

Collection membership is derived from the **current SourceRecord** rather than treated as an
independent authority. Revisions therefore remove stale membership.

All assessment attempts, including rejected ones, are persisted. The log is not claimed to be a
tamper-resistant ledger.

## Tests

```bash
pytest
```

The regression suite covers, among other cases:

- fabricated/unknown evidence IDs are rejected
- page locators are server-derived
- stale evidence is rejected after source revision
- `P` requires and preserves explicit conditions
- partial extraction cannot establish a complete text-surface review
- expected document surface is not inferred from ingested dictionary keys
- `NS` binds to the exact historical `review_id`
- a new review cannot revalidate an old NS assessment
- `NE` binds to an exact server-generated `MissingnessRecord`
- a new MissingnessRecord cannot revalidate an old NE assessment
- repeated creation of the same Missingness situation is idempotent and does not mutate `created_at`
- Unicode/whitespace representation variants resolve to the same canonical Missingness identity
- closing a later evidence gap changes current provenance, not historical admissibility
- collection revision removes stale membership
- declared semantic queries remain visibly unexecuted
- model-reported confidence has no effect on guards
- rejected attempts remain visible in the audit log

## Scope

v0.1.1.1 intentionally does **not** add semantic adjudication, native PDF/Zotero ingestion,
empirical PADC/DEA validation, multi-user authorization, a general governance-effectiveness
claim, or a cryptographically tamper-resistant audit ledger.

The governing implementation principle remains:

> **An agent may propose an evidence status, but it may not create the trusted facts that make
> that status structurally admissible.**

## License

MIT License. See `LICENSE`.
