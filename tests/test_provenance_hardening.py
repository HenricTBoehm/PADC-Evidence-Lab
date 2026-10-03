from padc_evidence_lab.evidence_store import EvidenceStore
from padc_evidence_lab.guards import validate_evidence_assessment
from padc_evidence_lab.schema import EpistemicStatus, EvidenceAssessmentProposal


def _record(store: EvidenceStore, proposal: EvidenceAssessmentProposal):
    result = validate_evidence_assessment(proposal, store)
    return store.record_assessment(proposal, result)


def test_partial_ingestion_cannot_establish_complete_text_review():
    store = EvidenceStore()
    source = store.ingest_source(
        item_id="DOC_001",
        title="Twelve-page document with incomplete extraction",
        pages={1: "Page one.", 12: "Page twelve."},
        collection_ids=["COLL_A"],
        expected_page_count=12,
    )

    manifest = source.extraction_manifest
    assert manifest is not None
    assert manifest.expected_page_count == 12
    assert manifest.extracted_page_numbers == [1, 12]
    assert manifest.missing_page_numbers == list(range(2, 12))
    assert manifest.extraction_complete is False
    assert manifest.declared_text_surface_complete is False

    claim = "No support exists for proposition X."
    review = store.run_document_review(item_id="DOC_001", claim=claim)
    assert review is not None
    assert review.pages_examined == [1, 12]
    assert review.fulltext_available is False
    assert review.protocol_complete is False

    result = validate_evidence_assessment(
        EvidenceAssessmentProposal(
            item_id="DOC_001",
            claim=claim,
            proposed_status=EpistemicStatus.NOT_SUPPORTED,
        ),
        store,
    )
    assert result.structurally_admissible is False
    assert result.guard_triggered == "INCOMPLETE_OR_MISSING_DOCUMENT_REVIEW"


def test_expected_surface_must_be_declared_not_inferred_from_ingested_pages():
    store = EvidenceStore()
    source = store.ingest_source(
        item_id="DOC_001",
        title="Unknown page surface",
        pages={1: "Only ingested page."},
        collection_ids=["COLL_A"],
    )
    manifest = source.extraction_manifest
    assert manifest is not None
    assert manifest.expected_page_numbers == []
    assert manifest.declared_text_surface_complete is False

    review = store.run_document_review(item_id="DOC_001", claim="Claim")
    assert review is not None
    assert review.protocol_complete is False


def test_new_review_cannot_revalidate_old_ns_assessment():
    store = EvidenceStore()
    store.ingest_source(
        item_id="DOC_001",
        title="Revision A",
        pages={1: "Alpha text."},
        collection_ids=["COLL_A"],
        expected_page_numbers=[1],
    )
    claim = "No support for proposition X."
    review_a = store.run_document_review(item_id="DOC_001", claim=claim)
    assert review_a is not None and store.review_is_current(review_a.review_id)

    assessment_a = _record(
        store,
        EvidenceAssessmentProposal(
            item_id="DOC_001",
            claim=claim,
            proposed_status=EpistemicStatus.NOT_SUPPORTED,
        ),
    )
    assert assessment_a.result.supporting_artifact_ids == [review_a.review_id]
    assert store.provenance_valid_for_record(assessment_a) is True

    store.ingest_source(
        item_id="DOC_001",
        title="Revision B",
        pages={1: "Beta text."},
        collection_ids=["COLL_A"],
        expected_page_numbers=[1],
    )
    assert store.provenance_valid_for_record(assessment_a) is False

    review_b = store.run_document_review(item_id="DOC_001", claim=claim)
    assert review_b is not None
    assert review_b.review_id != review_a.review_id
    assert store.review_is_current(review_b.review_id)

    # Historical assessment identity remains bound to Review A.
    assert assessment_a.result.supporting_artifact_ids == [review_a.review_id]
    assert store.provenance_valid_for_record(assessment_a) is False


def test_ne_binds_to_exact_missingness_record_and_is_not_revalidated_by_later_one():
    store = EvidenceStore()
    store.ingest_source(
        item_id="DOC_001",
        title="Incomplete revision A",
        pages={1: "Only page one is extracted."},
        collection_ids=["COLL_A"],
        expected_page_count=2,
    )
    claim = "Claim with incomplete evaluation surface."

    assessment_a = _record(
        store,
        EvidenceAssessmentProposal(
            item_id="DOC_001",
            claim=claim,
            proposed_status=EpistemicStatus.NON_EVALUABLE,
        ),
    )
    missingness_a_id = assessment_a.result.supporting_artifact_ids[0]
    assert missingness_a_id.startswith("MIS_")
    assert store.provenance_valid_for_record(assessment_a) is True

    store.ingest_source(
        item_id="DOC_001",
        title="Incomplete revision B",
        pages={1: "Revised but still incomplete."},
        collection_ids=["COLL_A"],
        expected_page_count=2,
    )
    assert store.provenance_valid_for_record(assessment_a) is False

    assessment_b = _record(
        store,
        EvidenceAssessmentProposal(
            item_id="DOC_001",
            claim=claim,
            proposed_status=EpistemicStatus.NON_EVALUABLE,
        ),
    )
    missingness_b_id = assessment_b.result.supporting_artifact_ids[0]
    assert missingness_b_id != missingness_a_id
    assert store.provenance_valid_for_record(assessment_b) is True
    assert store.provenance_valid_for_record(assessment_a) is False


def test_closing_later_gap_changes_current_provenance_not_historical_admissibility():
    store = EvidenceStore()
    store.ingest_source(
        item_id="DOC_001",
        title="Incomplete",
        pages={1: "Page one."},
        collection_ids=["COLL_A"],
        expected_page_count=2,
    )
    claim = "Claim initially non-evaluable."
    record = _record(
        store,
        EvidenceAssessmentProposal(
            item_id="DOC_001",
            claim=claim,
            proposed_status=EpistemicStatus.NON_EVALUABLE,
        ),
    )
    assert record.result.structurally_admissible is True
    assert store.provenance_valid_for_record(record) is True

    store.ingest_source(
        item_id="DOC_001",
        title="Complete",
        pages={1: "Page one.", 2: "Page two."},
        collection_ids=["COLL_A"],
        expected_page_count=2,
    )
    review = store.run_document_review(item_id="DOC_001", claim=claim)
    assert review is not None and store.review_is_current(review.review_id)

    assert record.result.structurally_admissible is True
    assert store.provenance_valid_for_record(record) is False


def test_collection_membership_is_rebuilt_from_current_source_revision():
    store = EvidenceStore()
    store.ingest_source(
        item_id="DOC_001",
        title="Revision A",
        pages={1: "Alpha."},
        collection_ids=["A"],
        expected_page_numbers=[1],
    )
    assert store.items_in_collection("A") == {"DOC_001"}

    store.ingest_source(
        item_id="DOC_001",
        title="Revision B",
        pages={1: "Beta."},
        collection_ids=["B"],
        expected_page_numbers=[1],
    )
    assert store.items_in_collection("A") == set()
    assert store.collection_exists("A") is False
    assert store.items_in_collection("B") == {"DOC_001"}


def test_semantic_queries_are_declared_but_not_misrepresented_as_executed():
    store = EvidenceStore()
    store.ingest_source(
        item_id="DOC_001",
        title="Complete",
        pages={1: "Alpha evidence."},
        collection_ids=["COLL_A"],
        expected_page_numbers=[1],
    )
    review = store.run_document_review(
        item_id="DOC_001",
        claim="Alpha claim",
        semantic_queries=["find semantically related passages"],
    )
    assert review is not None
    assert review.declared_semantic_queries_not_executed == [
        "find semantically related passages"
    ]
    assert review.semantic_search_executed is False
    assert review.semantic_search_adapter is None
    assert review.review_contract_hash
    assert review.executed_review_trace_hash
    assert review.review_contract_hash != review.executed_review_trace_hash


def test_admissible_output_is_explicitly_a_proposal_not_adjudication():
    store = EvidenceStore()
    store.ingest_source(
        item_id="DOC_001",
        title="Complete",
        pages={1: "Alpha evidence."},
        collection_ids=["COLL_A"],
        expected_page_numbers=[1],
    )
    evidence = store.find_evidence("DOC_001", "Alpha")[0]
    result = validate_evidence_assessment(
        EvidenceAssessmentProposal(
            item_id="DOC_001",
            claim="Alpha occurs.",
            proposed_status=EpistemicStatus.SUPPORTED,
            evidence_ids=[evidence.evidence_id],
        ),
        store,
    )
    assert result.structurally_admissible
    assert "STRUCTURALLY ADMISSIBLE PROPOSAL FOR S" in result.justification


def test_missingness_creation_is_idempotent_and_artifact_immutable():
    store = EvidenceStore()
    store.ingest_source(
        item_id="DOC_001",
        title="Incomplete",
        pages={1: "Page one."},
        collection_ids=["COLL_A"],
        expected_page_count=2,
    )

    first = store.create_missingness_record("DOC_001", "Claim with missing evidence")
    second = store.create_missingness_record("DOC_001", "Claim with missing evidence")

    assert first is not None and second is not None
    assert first.missingness_id == second.missingness_id
    assert second is first
    assert first.model_dump(mode="json") == second.model_dump(mode="json")


def test_missingness_claim_identity_uses_canonical_unicode_and_whitespace():
    store = EvidenceStore()
    store.ingest_source(
        item_id="DOC_001",
        title="Incomplete",
        pages={1: "Page one."},
        collection_ids=["COLL_A"],
        expected_page_count=2,
    )

    # First form uses decomposed e + combining acute and irregular whitespace;
    # second form uses NFC and ordinary spaces. These are representationally
    # different inputs but the same canonical claim artifact identity.
    first = store.create_missingness_record(
        "DOC_001", "  Cafe\u0301   claim\twith   missing evidence  "
    )
    second = store.create_missingness_record(
        "DOC_001", "Café claim with missing evidence"
    )

    assert first is not None and second is not None
    assert first.missingness_id == second.missingness_id
    assert second is first
    assert first.claim == "Café claim with missing evidence"
    assert first.model_dump(mode="json") == second.model_dump(mode="json")
