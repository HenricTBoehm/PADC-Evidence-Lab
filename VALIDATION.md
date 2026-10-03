# PADC Evidence Lab v0.1.1.1 — Validation Record

## Release designation

**Missingness Identity / Immutability Patch on the Source-Completeness and Provenance-Binding Hardened Prototype**

Target disposition: **HARDENED REFERENCE PROTOTYPE — FREEZE CANDIDATE**

## Research question

The v0.1.1 research question remains unchanged:

> Does the implemented Proposal/Evidence/Admissibility/Adjudication separation survive provenance
> counterexamples involving incomplete extraction surfaces, historical review substitution,
> missingness substitution, and stale derived collection state?

v0.1.1.1 adds one patch-level provenance invariant:

```text
stable server-derived artifact ID => immutable artifact content
```

For Missingness specifically:

```text
MIS_1 = MIS_2  =>  dump(MIS_1) = dump(MIS_2)
```

New claim identity is representation-normalized using Unicode NFC plus whitespace collapse before
hashing/storage. This is not semantic adjudication or semantic equivalence inference.

## Required counterexamples

The inherited v0.1.1 suite rejects or correctly reclassifies:

1. all ingested pages examined while the expected document text surface is incomplete;
2. a later review attempting to revalidate an NS assessment bound to an earlier review;
3. a later MissingnessRecord attempting to revalidate an NE assessment bound to an earlier record;
4. closing a later evidence gap changing historical admissibility rather than only current provenance;
5. collection membership surviving after the current source revision removes it;
6. declared semantic queries being represented as though they were executed.

v0.1.1.1 additionally tests:

7. repeated creation of an identical Missingness situation must return the identical immutable record;
8. canonically equivalent Unicode/whitespace claim representations must resolve to the same new Missingness artifact identity.

## Expected invariants

```text
Assessment identity is historical.
Provenance validity is revision-relative.
Derived state does not acquire independent authority.
Declared operation is not executed operation.
Structural admissibility is not semantic adjudication.
Stable artifact identity does not permit mutable artifact content.
```

## Current build-environment validation — v0.1.1.1

Executed in the ChatGPT build environment on 2026-10-03:

```text
Python      3.13.5
Pydantic    2.13.4
pytest      9.0.2
compileall  PASS
pytest      24/24 PASS
```

Commands:

```bash
python -m compileall -q src tests
PYTHONPATH=src python -m pytest -q
```

Direct Missingness idempotence probe in the same environment:

```text
SAME_ID          True
SAME_OBJECT      True
SAME_DUMP        True
CREATED_AT_SAME  True
CANONICAL_CLAIM  Café claim
```

Static source inspection confirms that `server.py` still contains exactly five `@mcp.tool()`
decorators and exposes no trusted-ingestion or direct MissingnessRecord-creation tool. This is a
static surface check, not a substitute for the runtime MCP smoke listed below.

The current sandbox does not have `mcp`, `hatchling`, or `build` installed and outbound package
installation is unavailable. Therefore the exact v0.1.1.1 ZIP has **not** been claimed here as
having passed a new MCP runtime smoke or wheel/sdist build in this environment.

## Independent release-artifact re-check reported for v0.1.1

After v0.1.1 was produced, an independent re-check reported by the Michelle Pre-Submission Review
System closed the previously open release-host checks for the **v0.1.1 artifact**:

```text
internal SHA-256 checks         PASS
compileall                      PASS
regression suite                22/22 PASS
MCP runtime with mcp 2.3.0      PASS
exactly five intended tools     PASS
wheel build                     PASS
sdist build                     PASS
wheel installation/import       PASS as v0.1.1
```

This independent result is retained as a separate provenance layer. It is not rewritten as though
those MCP/build checks were executed by the ChatGPT build environment, and it is not silently
promoted to an exact v0.1.1.1 package-build result. The v0.1.1.1 patch changes only claim
representation normalization, Missingness idempotence/immutability, tests, and release metadata;
the five-tool MCP surface and package dependency declarations are unchanged.

## Release-host revalidation commands for the exact v0.1.1.1 artifact

In a networked/release environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -c constraints.txt -e ".[dev]"
python -m compileall -q src tests
pytest -q
python -m build
```

Then start the stdio MCP server with MCP 2.3.0 and confirm that exactly these five tools are exposed:

```text
list_sources
find_evidence
run_document_review
validate_evidence_assessment
build_evidence_matrix
```

No trusted-ingestion or direct MissingnessRecord-creation tool may be exposed.

## Scope boundary

This validation is an implementation/provenance hardening exercise. It is not empirical validation
of PADC/DEA, semantic adjudication, a general governance-effectiveness result, production security
certification, or evidence that the JSON state store is tamper-resistant.
