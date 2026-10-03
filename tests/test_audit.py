from padc_evidence_lab.evidence_store import EvidenceStore
from padc_evidence_lab.guards import validate_evidence_assessment
from padc_evidence_lab.schema import (
    AssessmentStage,
    EpistemicStatus,
    EvidenceAssessmentProposal,
)


def _record(store, proposal):
    result = validate_evidence_assessment(proposal, store)
    return store.record_assessment(proposal, result)


def test_rejected_attempt_is_recorded():
    store = EvidenceStore()
    store.ingest_source(
        item_id="DOC_001",
        title="Doc",
        pages={1: "Some content."},
        collection_ids=["COLL_A"],
    )

    proposal = EvidenceAssessmentProposal(
        item_id="DOC_001",
        claim="Unsupported proposal",
        proposed_status=EpistemicStatus.SUPPORTED,
        evidence_ids=[],
    )
    record = _record(store, proposal)

    assert record.result.assessment_stage == AssessmentStage.REJECTED
    assert len(store.all_assessments()) == 1


def test_collection_filter_is_real():
    store = EvidenceStore()
    store.ingest_source(
        item_id="DOC_A",
        title="A",
        pages={1: "alpha evidence."},
        collection_ids=["COLL_A"],
    )
    store.ingest_source(
        item_id="DOC_B",
        title="B",
        pages={1: "beta evidence."},
        collection_ids=["COLL_B"],
    )

    ev_a = store.find_evidence("DOC_A", "alpha")[0]
    ev_b = store.find_evidence("DOC_B", "beta")[0]

    _record(
        store,
        EvidenceAssessmentProposal(
            item_id="DOC_A",
            claim="A claim",
            proposed_status=EpistemicStatus.SUPPORTED,
            evidence_ids=[ev_a.evidence_id],
        ),
    )
    _record(
        store,
        EvidenceAssessmentProposal(
            item_id="DOC_B",
            claim="B claim",
            proposed_status=EpistemicStatus.SUPPORTED,
            evidence_ids=[ev_b.evidence_id],
        ),
    )

    a_records = store.assessments_for_collection("COLL_A")
    b_records = store.assessments_for_collection("COLL_B")

    assert {r.proposal.item_id for r in a_records} == {"DOC_A"}
    assert {r.proposal.item_id for r in b_records} == {"DOC_B"}


def test_ns_provenance_valid_without_evidence_object():
    store = EvidenceStore()
    store.ingest_source(
        item_id="DOC_001",
        title="Doc",
        pages={1: "Some content."},
        collection_ids=["COLL_A"],
        expected_page_numbers=[1],
    )
    claim = "No support for this claim under the declared review protocol."
    store.run_document_review(item_id="DOC_001", claim=claim)

    proposal = EvidenceAssessmentProposal(
        item_id="DOC_001",
        claim=claim,
        proposed_status=EpistemicStatus.NOT_SUPPORTED,
    )
    record = _record(store, proposal)

    assert record.result.structurally_admissible
    assert record.result.evidence_ids == []
    assert store.provenance_valid_for_record(record) is True


def test_historical_admissibility_can_outlive_current_provenance():
    store = EvidenceStore()
    store.ingest_source(
        item_id="DOC_001",
        title="Doc",
        pages={1: "alpha evidence."},
        collection_ids=["COLL_A"],
    )
    ev = store.find_evidence("DOC_001", "alpha")[0]

    proposal = EvidenceAssessmentProposal(
        item_id="DOC_001",
        claim="Alpha is discussed.",
        proposed_status=EpistemicStatus.SUPPORTED,
        evidence_ids=[ev.evidence_id],
    )
    record = _record(store, proposal)
    assert record.result.structurally_admissible
    assert store.provenance_valid_for_record(record)

    store.ingest_source(
        item_id="DOC_001",
        title="Doc revised",
        pages={1: "different content."},
        collection_ids=["COLL_A"],
    )

    assert record.result.structurally_admissible is True
    assert store.provenance_valid_for_record(record) is False
