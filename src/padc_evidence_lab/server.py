from __future__ import annotations

import os
from typing import List

from mcp.server import MCPServer

from .evidence_store import EvidenceStore
from .guards import validate_evidence_assessment as _validate_assessment
from .schema import (
    AssessmentRecord,
    EvidenceAssessmentProposal,
    EvidenceMatrixResult,
    EvidenceMatrixRow,
    EvidenceObject,
    SourceSummary,
)


STATE_PATH = os.environ.get("PADC_EVIDENCE_STATE", "./data/evidence_state.json")

mcp = MCPServer("PADC Evidence Lab Engine")
store = EvidenceStore(STATE_PATH)


@mcp.tool()
def list_sources() -> List[SourceSummary]:
    """List current trusted source revisions and declared text-surface completeness."""
    return store.list_sources()


@mcp.tool()
def find_evidence(item_id: str, query: str, limit: int = 5) -> List[EvidenceObject]:
    """Search trusted page-indexed source text.

    Excerpts and page numbers are derived by the server; the agent cannot supply
    either field.
    """
    return store.find_evidence(item_id=item_id, query=query, limit=limit)


@mcp.tool()
def run_document_review(
    item_id: str,
    claim: str,
    search_terms: List[str] | None = None,
    semantic_queries: List[str] | None = None,
):
    """Run a server-side PAGE_INDEXED_TEXT review protocol for an exact claim.

    `protocol_complete` is derived from an explicitly declared complete text
    surface and page coverage. `semantic_queries` are stored as declared but are
    not executed in v0.1.1.1; the returned review states this explicitly.
    """
    return store.run_document_review(
        item_id=item_id,
        claim=claim,
        search_terms=search_terms or [],
        semantic_queries=semantic_queries or [],
    )


@mcp.tool()
def validate_evidence_assessment(
    proposal: EvidenceAssessmentProposal,
) -> AssessmentRecord:
    """Validate structural admissibility and persist every attempt.

    Passing means STRUCTURALLY ADMISSIBLE PROPOSAL FOR <status>; it does not
    semantically adjudicate the claim. NE is bound to a server-derived
    MissingnessRecord.
    """
    result = _validate_assessment(proposal, store)
    return store.record_assessment(proposal, result)


@mcp.tool()
def build_evidence_matrix(collection_id: str) -> EvidenceMatrixResult:
    """Build a current-collection-scoped audit matrix.

    `structurally_admissible` is historical; `provenance_valid` is re-computed
    using the exact historical provenance artifacts bound to each assessment.
    """
    records = store.assessments_for_collection(collection_id)
    rows: List[EvidenceMatrixRow] = []
    stage_counts: dict[str, int] = {}

    for record in records:
        stage = record.result.assessment_stage.value
        stage_counts[stage] = stage_counts.get(stage, 0) + 1

        rows.append(
            EvidenceMatrixRow(
                assessment_id=record.assessment_id,
                created_at=record.created_at,
                item_id=record.proposal.item_id,
                claim=record.proposal.claim,
                proposed_status=record.proposal.proposed_status,
                assessment_stage=record.result.assessment_stage,
                evidence_ids=list(record.result.evidence_ids),
                supporting_artifact_ids=list(record.result.supporting_artifact_ids),
                conditions=list(record.result.conditions),
                guard_triggered=record.result.guard_triggered,
                provenance_valid=store.provenance_valid_for_record(record),
                structurally_admissible=record.result.structurally_admissible,
                adjudicated_status=None,
            )
        )

    return EvidenceMatrixResult(
        collection_id=collection_id,
        total_assessments=len(rows),
        stage_counts=stage_counts,
        rows=rows,
    )


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
