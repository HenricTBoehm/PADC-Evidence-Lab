import pytest

from padc_evidence_lab.evidence_store import EvidenceStore
from padc_evidence_lab.guards import validate_evidence_assessment
from padc_evidence_lab.schema import (
    AssessmentStage,
    EpistemicStatus,
    EvidenceAssessmentProposal,
)


@pytest.fixture
def store():
    s = EvidenceStore()
    s.ingest_source(
        item_id="DOC_001",
        title="System Theory",
        pages={
            1: "Introduction to systems theory.",
            12: (
                "Autopoietische Systeme reproduzieren ihre eigenen Elemente. "
                "Direkte Fremdsteuerung ist strukturell ausgeschlossen."
            ),
        },
        collection_ids=["COLL_A"],
        expected_page_numbers=[1, 12],
    )
    return s


def test_server_derives_page_locator(store):
    evidence = store.find_evidence("DOC_001", "Autopoietische Elemente")
    assert evidence
    assert evidence[0].page_number == 12
    assert store.evidence_is_current(evidence[0].evidence_id)


def test_agent_cannot_reference_unknown_evidence(store):
    proposal = EvidenceAssessmentProposal(
        item_id="DOC_001",
        claim="Autopoiesis is present.",
        proposed_status=EpistemicStatus.SUPPORTED,
        evidence_ids=["EV_FAKE"],
    )
    result = validate_evidence_assessment(proposal, store)
    assert not result.structurally_admissible
    assert result.assessment_stage == AssessmentStage.REJECTED
    assert result.guard_triggered == "UNKNOWN_EVIDENCE_ID"


def test_supported_requires_current_evidence(store):
    evidence = store.find_evidence("DOC_001", "Autopoietische Systeme")[0]
    proposal = EvidenceAssessmentProposal(
        item_id="DOC_001",
        claim="The paper discusses autopoietic systems.",
        proposed_status=EpistemicStatus.SUPPORTED,
        evidence_ids=[evidence.evidence_id],
    )
    result = validate_evidence_assessment(proposal, store)
    assert result.structurally_admissible
    assert result.assessment_stage == AssessmentStage.ADMISSIBLE


def test_stale_evidence_rejected_after_source_revision(store):
    evidence = store.find_evidence("DOC_001", "Autopoietische Systeme")[0]

    store.ingest_source(
        item_id="DOC_001",
        title="System Theory - revised",
        pages={
            1: "Revised introduction.",
            12: "This revision contains materially different wording.",
        },
        collection_ids=["COLL_A"],
    )

    proposal = EvidenceAssessmentProposal(
        item_id="DOC_001",
        claim="The paper discusses autopoietic systems.",
        proposed_status=EpistemicStatus.SUPPORTED,
        evidence_ids=[evidence.evidence_id],
    )
    result = validate_evidence_assessment(proposal, store)

    assert not result.structurally_admissible
    assert result.guard_triggered == "STALE_OR_INVALID_EVIDENCE"


def test_partial_support_requires_conditions_and_preserves_them(store):
    evidence = store.find_evidence("DOC_001", "Fremdsteuerung")[0]

    failed = EvidenceAssessmentProposal(
        item_id="DOC_001",
        claim="External control is impossible in every sense.",
        proposed_status=EpistemicStatus.PARTIALLY_SUPPORTED,
        evidence_ids=[evidence.evidence_id],
        conditions=[],
    )
    failed_result = validate_evidence_assessment(failed, store)
    assert not failed_result.structurally_admissible
    assert failed_result.guard_triggered == "MISSING_CONDITIONS"

    passed = EvidenceAssessmentProposal(
        item_id="DOC_001",
        claim="External control is impossible in every sense.",
        proposed_status=EpistemicStatus.PARTIALLY_SUPPORTED,
        evidence_ids=[evidence.evidence_id],
        conditions=["Only under the source's structural-control framing."],
    )
    passed_result = validate_evidence_assessment(passed, store)
    assert passed_result.structurally_admissible
    assert passed_result.conditions == [
        "Only under the source's structural-control framing."
    ]


def test_ns_requires_review_for_exact_claim(store):
    claim_a = "The source supports proposition A."
    claim_b = "The source supports proposition B."

    review = store.run_document_review(
        item_id="DOC_001",
        claim=claim_a,
        search_terms=["proposition"],
    )
    assert review is not None
    assert review.protocol_complete

    proposal_b = EvidenceAssessmentProposal(
        item_id="DOC_001",
        claim=claim_b,
        proposed_status=EpistemicStatus.NOT_SUPPORTED,
    )
    result_b = validate_evidence_assessment(proposal_b, store)
    assert not result_b.structurally_admissible
    assert result_b.guard_triggered == "INCOMPLETE_OR_MISSING_DOCUMENT_REVIEW"

    proposal_a = EvidenceAssessmentProposal(
        item_id="DOC_001",
        claim=claim_a,
        proposed_status=EpistemicStatus.NOT_SUPPORTED,
    )
    result_a = validate_evidence_assessment(proposal_a, store)
    assert result_a.structurally_admissible
    assert result_a.supporting_artifact_ids == [review.review_id]


def test_ne_rejected_after_complete_current_review(store):
    claim = "A fully reviewed claim."
    store.run_document_review(item_id="DOC_001", claim=claim)

    proposal = EvidenceAssessmentProposal(
        item_id="DOC_001",
        claim=claim,
        proposed_status=EpistemicStatus.NON_EVALUABLE,
    )
    result = validate_evidence_assessment(proposal, store)

    assert not result.structurally_admissible
    assert result.guard_triggered == "INVALID_NON_EVALUABLE"


def test_confidence_does_not_override_missing_evidence(store):
    proposal = EvidenceAssessmentProposal(
        item_id="DOC_001",
        claim="High confidence unsupported proposal.",
        proposed_status=EpistemicStatus.SUPPORTED,
        evidence_ids=[],
        model_reported_confidence=0.99,
    )
    result = validate_evidence_assessment(proposal, store)

    assert not result.structurally_admissible
    assert result.model_reported_confidence == 0.99
    assert result.guard_triggered == "MISSING_EVIDENCE_IDS"
