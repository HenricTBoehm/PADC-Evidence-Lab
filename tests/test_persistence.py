from padc_evidence_lab.evidence_store import EvidenceStore


def test_persistent_state_roundtrip(tmp_path):
    path = tmp_path / "state.json"

    store = EvidenceStore(path)
    source = store.ingest_source(
        item_id="DOC_001",
        title="Persistent Doc",
        pages={1: "Persistent page text."},
        collection_ids=["COLL_A"],
    )
    evidence = store.find_evidence("DOC_001", "Persistent")

    reloaded = EvidenceStore(path)
    current = reloaded.current_source("DOC_001")

    assert current is not None
    assert current.source_id == source.source_id
    assert reloaded.collection_exists("COLL_A")
    assert evidence
    assert reloaded.evidence_is_current(evidence[0].evidence_id)


def test_legacy_v010_state_loads_without_inheriting_completeness_authority(tmp_path):
    import json

    path = tmp_path / "legacy_state.json"
    path.write_text(
        json.dumps(
            {
                "sources": {
                    "SRC_old": {
                        "source_id": "SRC_old",
                        "item_id": "DOC_OLD",
                        "title": "Legacy",
                        "revision": 1,
                        "text_sha256": "legacy-hash",
                        "artifact_sha256": None,
                        "pages": {"1": "Legacy page text."},
                        "collection_ids": ["CURRENT"],
                    }
                },
                "current_source_by_item": {"DOC_OLD": "SRC_old"},
                "collections": {"STALE_DERIVED_INDEX": ["DOC_OLD"]},
                "evidence_registry": {},
                "review_registry": {},
                "assessments": [],
            }
        ),
        encoding="utf-8",
    )

    store = EvidenceStore(path)
    source = store.current_source("DOC_OLD")
    assert source is not None
    assert source.extraction_manifest is None
    assert store.collection_exists("CURRENT")
    assert not store.collection_exists("STALE_DERIVED_INDEX")

    review = store.run_document_review(item_id="DOC_OLD", claim="Legacy claim")
    assert review is not None
    assert review.fulltext_available is False
    assert review.protocol_complete is False
