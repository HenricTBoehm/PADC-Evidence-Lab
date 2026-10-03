from __future__ import annotations

from .evidence_store import EvidenceStore
from .schema import (
    AdmissibilityResult,
    AssessmentStage,
    EpistemicStatus,
    EvidenceAssessmentProposal,
)


def _reject(
    proposal: EvidenceAssessmentProposal,
    *,
    guard: str,
    justification: str,
    evidence_ids: list[str] | None = None,
    supporting_artifact_ids: list[str] | None = None,
) -> AdmissibilityResult:
    return AdmissibilityResult(
        item_id=proposal.item_id,
        claim=proposal.claim,
        proposed_status=proposal.proposed_status,
        assessment_stage=AssessmentStage.REJECTED,
        structurally_admissible=False,
        guard_triggered=guard,
        evidence_ids=list(evidence_ids or proposal.evidence_ids),
        supporting_artifact_ids=list(supporting_artifact_ids or []),
        conditions=[c.strip() for c in proposal.conditions if c.strip()],
        justification=justification,
        model_reported_confidence=proposal.model_reported_confidence,
    )


def _admissible_label(status: EpistemicStatus) -> str:
    return f"STRUCTURALLY ADMISSIBLE PROPOSAL FOR {status.value}"


def validate_evidence_assessment(
    proposal: EvidenceAssessmentProposal,
    store: EvidenceStore,
) -> AdmissibilityResult:
    """Deterministic structural-admissibility guard.

    The guard does not adjudicate semantic truth. For NE, it may create a
    server-derived MissingnessRecord so the assessment binds to a concrete
    evaluability-failure artifact rather than to an absence inferred later.
    """
    status = proposal.proposed_status
    item_id = proposal.item_id
    clean_conditions = [c.strip() for c in proposal.conditions if c.strip()]

    if store.current_source(item_id) is None:
        if status == EpistemicStatus.NON_EVALUABLE:
            missingness = store.create_missingness_record(item_id, proposal.claim)
            if missingness is None:
                return _reject(
                    proposal,
                    guard="MISSINGNESS_NOT_ESTABLISHED",
                    justification="REJECTED NE: Server-side missingness was not established.",
                )
            return AdmissibilityResult(
                item_id=item_id,
                claim=proposal.claim,
                proposed_status=status,
                assessment_stage=AssessmentStage.ADMISSIBLE,
                structurally_admissible=True,
                evidence_ids=[],
                supporting_artifact_ids=[missingness.missingness_id],
                conditions=clean_conditions,
                justification=(
                    f"{_admissible_label(status)}: Server-derived missingness records "
                    "that no current trusted source is available."
                ),
                model_reported_confidence=proposal.model_reported_confidence,
            )
        return _reject(
            proposal,
            guard="NO_TRUSTED_SOURCE",
            justification=f"REJECTED {status.value}: No current trusted source is registered.",
        )

    if status in {
        EpistemicStatus.SUPPORTED,
        EpistemicStatus.PARTIALLY_SUPPORTED,
        EpistemicStatus.CONTRADICTED,
    }:
        if not proposal.evidence_ids:
            return _reject(
                proposal,
                guard="MISSING_EVIDENCE_IDS",
                justification=(
                    f"REJECTED {status.value}: At least one server-generated "
                    "EvidenceObject ID is required."
                ),
            )

        for ev_id in proposal.evidence_ids:
            evidence = store.get_evidence(ev_id)
            if evidence is None:
                return _reject(
                    proposal,
                    guard="UNKNOWN_EVIDENCE_ID",
                    justification=(
                        f"REJECTED {status.value}: Evidence '{ev_id}' does not exist."
                    ),
                    evidence_ids=[ev_id],
                )

            if evidence.item_id != item_id:
                return _reject(
                    proposal,
                    guard="ITEM_ID_MISMATCH",
                    justification=(
                        f"REJECTED {status.value}: Evidence '{ev_id}' belongs to "
                        f"'{evidence.item_id}', not '{item_id}'."
                    ),
                    evidence_ids=[ev_id],
                )

            if not store.evidence_is_current(ev_id):
                return _reject(
                    proposal,
                    guard="STALE_OR_INVALID_EVIDENCE",
                    justification=(
                        f"REJECTED {status.value}: Evidence '{ev_id}' does not validate "
                        "against the current trusted source revision."
                    ),
                    evidence_ids=[ev_id],
                )

        if status == EpistemicStatus.PARTIALLY_SUPPORTED and not clean_conditions:
            return _reject(
                proposal,
                guard="MISSING_CONDITIONS",
                justification=(
                    "REJECTED P: Partially Supported requires at least one explicit "
                    "condition or limitation."
                ),
                supporting_artifact_ids=list(proposal.evidence_ids),
            )

        return AdmissibilityResult(
            item_id=item_id,
            claim=proposal.claim,
            proposed_status=status,
            assessment_stage=AssessmentStage.ADMISSIBLE,
            structurally_admissible=True,
            evidence_ids=list(proposal.evidence_ids),
            supporting_artifact_ids=list(proposal.evidence_ids),
            conditions=clean_conditions,
            justification=(
                f"{_admissible_label(status)}: The proposal satisfies the "
                "evidence-admissibility requirements."
            ),
            model_reported_confidence=proposal.model_reported_confidence,
        )

    if status == EpistemicStatus.NOT_SUPPORTED:
        review = store.get_current_document_review(item_id, proposal.claim)
        if review is None or not store.review_is_current(review.review_id):
            return _reject(
                proposal,
                guard="INCOMPLETE_OR_MISSING_DOCUMENT_REVIEW",
                justification=(
                    "REJECTED NS: Not Supported requires a current, claim-specific, "
                    "protocol-complete server-generated DocumentReview over a declared "
                    "complete PAGE_INDEXED_TEXT surface."
                ),
            )

        return AdmissibilityResult(
            item_id=item_id,
            claim=proposal.claim,
            proposed_status=status,
            assessment_stage=AssessmentStage.ADMISSIBLE,
            structurally_admissible=True,
            evidence_ids=[],
            supporting_artifact_ids=[review.review_id],
            conditions=clean_conditions,
            justification=(
                f"{_admissible_label(status)}: A current, claim-specific, "
                "protocol-complete DocumentReview is bound to this assessment."
            ),
            model_reported_confidence=proposal.model_reported_confidence,
        )

    if status == EpistemicStatus.NON_EVALUABLE:
        review = store.get_current_document_review(item_id, proposal.claim)
        if review is not None and store.review_is_current(review.review_id):
            return _reject(
                proposal,
                guard="INVALID_NON_EVALUABLE",
                justification=(
                    "REJECTED NE: A current, claim-specific, protocol-complete "
                    "DocumentReview already establishes evaluability under the declared "
                    "PAGE_INDEXED_TEXT protocol."
                ),
                supporting_artifact_ids=[review.review_id],
            )

        missingness = store.create_missingness_record(item_id, proposal.claim)
        if missingness is None:
            return _reject(
                proposal,
                guard="MISSINGNESS_NOT_ESTABLISHED",
                justification="REJECTED NE: Server-side missingness was not established.",
            )

        return AdmissibilityResult(
            item_id=item_id,
            claim=proposal.claim,
            proposed_status=status,
            assessment_stage=AssessmentStage.ADMISSIBLE,
            structurally_admissible=True,
            evidence_ids=[],
            supporting_artifact_ids=[missingness.missingness_id],
            conditions=clean_conditions,
            justification=(
                f"{_admissible_label(status)}: Server-derived MissingnessRecord "
                "documents the current evaluability gap."
            ),
            model_reported_confidence=proposal.model_reported_confidence,
        )

    return _reject(
        proposal,
        guard="UNSUPPORTED_STATUS",
        justification=f"REJECTED: Unsupported status {status}.",
    )
