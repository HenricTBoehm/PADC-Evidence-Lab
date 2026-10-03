from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Optional
from uuid import uuid4

from .normalization import canonicalize_claim
from .schema import (
    AdmissibilityResult,
    AssessmentRecord,
    DocumentReview,
    EpistemicStatus,
    EvidenceAssessmentProposal,
    EvidenceObject,
    ExtractionManifest,
    MissingnessRecord,
    SourceRecord,
    SourceSummary,
    SurfaceType,
)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _canonical_pages_text(pages: Dict[int, str]) -> str:
    payload = {str(k): pages[k] for k in sorted(pages)}
    return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _claim_hash(claim: str) -> str:
    return _sha256_text(canonicalize_claim(claim))


def _tokenize(value: str) -> List[str]:
    return [t for t in re.findall(r"\w+", value.lower(), flags=re.UNICODE) if len(t) >= 3]


def _sentence_spans(text: str) -> Iterable[tuple[int, int, str]]:
    """Lightweight deterministic sentence-ish segmentation."""
    start = 0
    for match in re.finditer(r"(?<=[.!?])\s+", text):
        end = match.start()
        snippet = text[start:end].strip()
        if snippet:
            real_start = text.find(snippet, start, end + 1)
            yield real_start, real_start + len(snippet), snippet
        start = match.end()

    snippet = text[start:].strip()
    if snippet:
        real_start = text.find(snippet, start)
        yield real_start, real_start + len(snippet), snippet


def _normalized_page_numbers(values: Optional[List[int]]) -> List[int]:
    if not values:
        return []
    pages = sorted({int(v) for v in values})
    if any(v <= 0 for v in pages):
        raise ValueError("Expected page numbers must be positive integers.")
    return pages


def _build_extraction_manifest(
    *,
    extracted_page_numbers: List[int],
    expected_page_count: Optional[int],
    expected_page_numbers: Optional[List[int]],
    extraction_method: str,
    extraction_version: str,
    excluded_modalities: Optional[List[str]],
) -> ExtractionManifest:
    extracted = sorted(set(extracted_page_numbers))
    expected = _normalized_page_numbers(expected_page_numbers)

    if expected_page_count is not None:
        if expected_page_count <= 0:
            raise ValueError("expected_page_count must be positive.")
        count_surface = list(range(1, expected_page_count + 1))
        if expected and expected != count_surface:
            raise ValueError(
                "expected_page_count and expected_page_numbers describe different surfaces."
            )
        expected = count_surface

    effective_count = len(expected) if expected else None
    missing = sorted(set(expected) - set(extracted)) if expected else []
    unexpected = sorted(set(extracted) - set(expected)) if expected else []
    extraction_complete = bool(expected) and not missing and not unexpected

    modalities = sorted(
        {
            m.strip().upper()
            for m in (excluded_modalities or ["IMAGES", "TABLE_STRUCTURE", "EMBEDDED_FILES"])
            if m.strip()
        }
    )

    payload = {
        "surface_type": SurfaceType.PAGE_INDEXED_TEXT.value,
        "expected_page_count": effective_count,
        "expected_page_numbers": expected,
        "extracted_page_numbers": extracted,
        "missing_page_numbers": missing,
        "unexpected_page_numbers": unexpected,
        "extraction_complete": extraction_complete,
        "declared_text_surface_complete": extraction_complete,
        "excluded_modalities": modalities,
        "extraction_method": extraction_method,
        "extraction_version": extraction_version,
    }
    manifest_hash = _sha256_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    )
    return ExtractionManifest(**payload, extraction_manifest_hash=manifest_hash)


class EvidenceStore:
    """Persistent JSON-backed research prototype store.

    Trusted ingestion writes source records out-of-band. MCP-facing operations can
    only read/search those sources and create derived evidence/review/assessment
    artifacts. Host-level write protection is outside this MCP capability boundary.
    """

    def __init__(self, state_path: Optional[str | Path] = None):
        self.state_path = Path(state_path) if state_path else None

        self._sources: Dict[str, SourceRecord] = {}
        self._current_source_by_item: Dict[str, str] = {}
        self._collections: Dict[str, set[str]] = {}
        self._evidence_registry: Dict[str, EvidenceObject] = {}
        self._review_registry: Dict[str, DocumentReview] = {}
        self._missingness_registry: Dict[str, MissingnessRecord] = {}
        self._assessments: List[AssessmentRecord] = []

        if self.state_path and self.state_path.exists():
            self._load()

    # ---------- persistence ----------

    def _serialize(self) -> dict:
        return {
            "sources": {k: v.model_dump(mode="json") for k, v in self._sources.items()},
            "current_source_by_item": dict(self._current_source_by_item),
            # Collections are serialized for inspection only; they are reconstructed
            # from current SourceRecords on load and after each source revision.
            "collections": {k: sorted(v) for k, v in self._collections.items()},
            "evidence_registry": {
                k: v.model_dump(mode="json") for k, v in self._evidence_registry.items()
            },
            "review_registry": {
                k: v.model_dump(mode="json") for k, v in self._review_registry.items()
            },
            "missingness_registry": {
                k: v.model_dump(mode="json") for k, v in self._missingness_registry.items()
            },
            "assessments": [v.model_dump(mode="json") for v in self._assessments],
        }

    def _persist(self) -> None:
        if not self.state_path:
            return
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(self.state_path.suffix + ".tmp")
        tmp.write_text(
            json.dumps(self._serialize(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        os.replace(tmp, self.state_path)

    def _rebuild_collections(self) -> None:
        rebuilt: Dict[str, set[str]] = {}
        for item_id in sorted(self._current_source_by_item):
            source = self.current_source(item_id)
            if source is None:
                continue
            for collection_id in source.collection_ids:
                rebuilt.setdefault(collection_id, set()).add(item_id)
        self._collections = rebuilt

    def _load(self) -> None:
        raw = json.loads(self.state_path.read_text(encoding="utf-8"))
        self._sources = {
            k: SourceRecord.model_validate(v) for k, v in raw.get("sources", {}).items()
        }
        self._current_source_by_item = dict(raw.get("current_source_by_item", {}))
        self._evidence_registry = {
            k: EvidenceObject.model_validate(v)
            for k, v in raw.get("evidence_registry", {}).items()
        }
        self._review_registry = {
            k: DocumentReview.model_validate(v)
            for k, v in raw.get("review_registry", {}).items()
        }
        self._missingness_registry = {
            k: MissingnessRecord.model_validate(v)
            for k, v in raw.get("missingness_registry", {}).items()
        }
        self._assessments = [
            AssessmentRecord.model_validate(v) for v in raw.get("assessments", [])
        ]
        # Never trust a persisted derived collection index as an authority.
        self._rebuild_collections()

    # ---------- trusted ingestion (NOT MCP tools) ----------

    def ingest_source(
        self,
        *,
        item_id: str,
        title: str,
        pages: Dict[int, str],
        collection_ids: Optional[List[str]] = None,
        artifact_sha256: Optional[str] = None,
        expected_page_count: Optional[int] = None,
        expected_page_numbers: Optional[List[int]] = None,
        extraction_method: str = "trusted_page_json_v2",
        extraction_version: str = "0.1.1",
        excluded_modalities: Optional[List[str]] = None,
    ) -> SourceRecord:
        """Trusted-side ingestion only.

        Re-ingesting an item creates a new immutable source revision and moves
        the current-source pointer. Completeness is never inferred merely from
        the pages that happen to be ingested: an expected PAGE_INDEXED_TEXT
        surface must be explicitly declared by trusted ingestion.
        """
        cleaned_pages = {
            int(page): text.strip()
            for page, text in pages.items()
            if int(page) > 0 and isinstance(text, str) and text.strip()
        }
        if not cleaned_pages:
            raise ValueError("A source must contain at least one non-empty page.")

        manifest = _build_extraction_manifest(
            extracted_page_numbers=sorted(cleaned_pages),
            expected_page_count=expected_page_count,
            expected_page_numbers=expected_page_numbers,
            extraction_method=extraction_method,
            extraction_version=extraction_version,
            excluded_modalities=excluded_modalities,
        )

        previous = self.current_source(item_id)
        revision = 1 if previous is None else previous.revision + 1
        text_sha256 = _sha256_text(_canonical_pages_text(cleaned_pages))
        source_id = "SRC_" + _sha256_text(
            f"{item_id}|{revision}|{text_sha256}|{manifest.extraction_manifest_hash}"
        )[:20]

        source = SourceRecord(
            source_id=source_id,
            item_id=item_id,
            title=title.strip() or item_id,
            revision=revision,
            text_sha256=text_sha256,
            artifact_sha256=artifact_sha256,
            pages=cleaned_pages,
            collection_ids=sorted(set(collection_ids or [])),
            extraction_manifest=manifest,
        )

        self._sources[source_id] = source
        self._current_source_by_item[item_id] = source_id
        self._rebuild_collections()
        self._persist()
        return source

    # ---------- source access ----------

    def current_source(self, item_id: str) -> Optional[SourceRecord]:
        source_id = self._current_source_by_item.get(item_id)
        return self._sources.get(source_id) if source_id else None

    def list_sources(self) -> List[SourceSummary]:
        result: List[SourceSummary] = []
        for item_id in sorted(self._current_source_by_item):
            source = self.current_source(item_id)
            if not source:
                continue
            manifest = source.extraction_manifest
            result.append(
                SourceSummary(
                    item_id=source.item_id,
                    source_id=source.source_id,
                    title=source.title,
                    revision=source.revision,
                    pages_total=len(source.pages),
                    pages_ingested=len(source.pages),
                    expected_page_count=(manifest.expected_page_count if manifest else None),
                    expected_page_numbers=(manifest.expected_page_numbers if manifest else []),
                    missing_page_numbers=(manifest.missing_page_numbers if manifest else []),
                    declared_text_surface_complete=(
                        manifest.declared_text_surface_complete if manifest else False
                    ),
                    extraction_manifest_hash=(
                        manifest.extraction_manifest_hash if manifest else None
                    ),
                    text_sha256=source.text_sha256,
                    artifact_sha256=source.artifact_sha256,
                    collection_ids=source.collection_ids,
                )
            )
        return result

    def collection_exists(self, collection_id: str) -> bool:
        return collection_id in self._collections

    def items_in_collection(self, collection_id: str) -> set[str]:
        return set(self._collections.get(collection_id, set()))

    # ---------- server-derived evidence ----------

    def find_evidence(
        self, item_id: str, query: str, limit: int = 5
    ) -> List[EvidenceObject]:
        source = self.current_source(item_id)
        if source is None:
            return []

        tokens = set(_tokenize(query))
        if not tokens:
            return []

        candidates: List[tuple[int, int, int, int, str]] = []
        for page_number in sorted(source.pages):
            page_text = source.pages[page_number]
            for start, end, snippet in _sentence_spans(page_text):
                snippet_tokens = set(_tokenize(snippet))
                score = len(tokens & snippet_tokens)
                if score > 0:
                    candidates.append((score, page_number, start, end, snippet))

        candidates.sort(key=lambda x: (-x[0], x[1], x[2]))

        output: List[EvidenceObject] = []
        for _, page_number, start, end, snippet in candidates[: max(1, min(limit, 20))]:
            page_text = source.pages[page_number]
            evidence_id = "EV_" + _sha256_text(
                f"{source.source_id}|{page_number}|{start}|{end}|{snippet}"
            )[:20]

            evidence = EvidenceObject(
                evidence_id=evidence_id,
                item_id=item_id,
                source_id=source.source_id,
                source_revision=source.revision,
                page_number=page_number,
                verbatim_excerpt=snippet,
                source_text_hash=source.text_sha256,
                page_hash=_sha256_text(page_text),
                excerpt_hash=_sha256_text(snippet),
                char_start=start,
                char_end=end,
                extraction_method="server_page_search_v1",
            )
            self._evidence_registry[evidence_id] = evidence
            output.append(evidence)

        if output:
            self._persist()
        return output

    def get_evidence(self, evidence_id: str) -> Optional[EvidenceObject]:
        return self._evidence_registry.get(evidence_id)

    def evidence_is_current(self, evidence_id: str) -> bool:
        ev = self.get_evidence(evidence_id)
        if ev is None:
            return False

        source = self.current_source(ev.item_id)
        if source is None:
            return False

        if (
            source.source_id != ev.source_id
            or source.revision != ev.source_revision
            or source.text_sha256 != ev.source_text_hash
        ):
            return False

        page_text = source.pages.get(ev.page_number)
        if page_text is None or _sha256_text(page_text) != ev.page_hash:
            return False

        if ev.char_end > len(page_text):
            return False

        excerpt_at_span = page_text[ev.char_start : ev.char_end]
        return (
            excerpt_at_span == ev.verbatim_excerpt
            and _sha256_text(ev.verbatim_excerpt) == ev.excerpt_hash
        )

    def evidence_ids_all_current(
        self, evidence_ids: List[str], *, item_id: Optional[str] = None
    ) -> bool:
        if not evidence_ids:
            return False
        for ev_id in evidence_ids:
            ev = self.get_evidence(ev_id)
            if ev is None:
                return False
            if item_id is not None and ev.item_id != item_id:
                return False
            if not self.evidence_is_current(ev_id):
                return False
        return True

    # ---------- server-derived document reviews ----------

    def run_document_review(
        self,
        *,
        item_id: str,
        claim: str,
        search_terms: Optional[List[str]] = None,
        semantic_queries: Optional[List[str]] = None,
    ) -> Optional[DocumentReview]:
        source = self.current_source(item_id)
        if source is None:
            return None

        manifest = source.extraction_manifest
        canonical_claim = canonicalize_claim(claim)
        declared_terms = [t.strip() for t in (search_terms or []) if t.strip()]
        claim_terms = _tokenize(canonical_claim)
        effective_terms = sorted(set(claim_terms + declared_terms))
        declared_semantic_queries = [
            q.strip() for q in (semantic_queries or []) if q.strip()
        ]

        # The executed v0.1.1.1 protocol is PAGE_INDEXED_TEXT traversal plus lexical
        # evidence search. Semantic queries are declarations only until an adapter exists.
        pages_examined = sorted(source.pages)
        matched_ids: List[str] = []
        for term in effective_terms:
            for ev in self.find_evidence(item_id, term, limit=20):
                if ev.evidence_id not in matched_ids:
                    matched_ids.append(ev.evidence_id)

        expected_pages = manifest.expected_page_numbers if manifest else []
        declared_text_surface_complete = bool(
            manifest and manifest.declared_text_surface_complete
        )
        protocol_complete_text = bool(
            manifest
            and declared_text_surface_complete
            and pages_examined == expected_pages
        )
        claim_hash = _claim_hash(canonical_claim)

        contract_material = {
            "source_id": source.source_id,
            "source_revision": source.revision,
            "claim_hash": claim_hash,
            "protocol_name": "page_indexed_text_scan_v2",
            "surface_type": SurfaceType.PAGE_INDEXED_TEXT.value,
            "extraction_manifest_hash": (
                manifest.extraction_manifest_hash if manifest else None
            ),
            "search_terms": effective_terms,
            "declared_semantic_queries_not_executed": declared_semantic_queries,
        }
        review_contract_hash = _sha256_text(
            json.dumps(
                contract_material, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
        )

        execution_material = {
            "source_id": source.source_id,
            "claim_hash": claim_hash,
            "pages_examined": pages_examined,
            "matched_evidence_ids": sorted(matched_ids),
            "semantic_search_executed": False,
            "semantic_search_adapter": None,
        }
        executed_review_trace_hash = _sha256_text(
            json.dumps(
                execution_material, ensure_ascii=False, sort_keys=True, separators=(",", ":")
            )
        )

        review_id = "REV_" + _sha256_text(
            f"{review_contract_hash}|{executed_review_trace_hash}"
        )[:20]

        review = DocumentReview(
            review_id=review_id,
            item_id=item_id,
            claim=canonical_claim,
            claim_hash=claim_hash,
            source_id=source.source_id,
            source_revision=source.revision,
            source_text_hash=source.text_sha256,
            pages_total=len(source.pages),
            expected_page_count=(manifest.expected_page_count if manifest else None),
            expected_page_numbers=expected_pages,
            pages_examined=pages_examined,
            surface_type=SurfaceType.PAGE_INDEXED_TEXT,
            extraction_manifest_hash=(
                manifest.extraction_manifest_hash if manifest else None
            ),
            declared_text_surface_complete=declared_text_surface_complete,
            search_terms=effective_terms,
            declared_semantic_queries_not_executed=declared_semantic_queries,
            semantic_search_executed=False,
            semantic_search_adapter=None,
            review_contract_hash=review_contract_hash,
            executed_review_trace_hash=executed_review_trace_hash,
            protocol_name="page_indexed_text_scan_v2",
            fulltext_available=declared_text_surface_complete,
            protocol_complete=protocol_complete_text,
            matched_evidence_ids=matched_ids,
        )

        self._review_registry[review_id] = review
        self._persist()
        return review

    def get_review(self, review_id: str) -> Optional[DocumentReview]:
        return self._review_registry.get(review_id)

    def get_current_document_review(
        self, item_id: str, claim: str
    ) -> Optional[DocumentReview]:
        source = self.current_source(item_id)
        if source is None:
            return None

        wanted_hash = _claim_hash(claim)
        matches = [
            review
            for review in self._review_registry.values()
            if review.item_id == item_id
            and review.claim_hash == wanted_hash
            and review.source_id == source.source_id
            and review.source_revision == source.revision
            and review.source_text_hash == source.text_sha256
        ]
        if not matches:
            return None
        matches.sort(key=lambda r: r.review_id)
        return matches[-1]

    def review_is_current(self, review_id: str) -> bool:
        review = self._review_registry.get(review_id)
        if review is None:
            return False
        source = self.current_source(review.item_id)
        if source is None or source.extraction_manifest is None:
            return False
        manifest = source.extraction_manifest
        return bool(
            source.source_id == review.source_id
            and source.revision == review.source_revision
            and source.text_sha256 == review.source_text_hash
            and review.extraction_manifest_hash == manifest.extraction_manifest_hash
            and review.surface_type == manifest.surface_type
            and review.declared_text_surface_complete
            and manifest.declared_text_surface_complete
            and review.fulltext_available
            and review.protocol_complete
            and review.expected_page_numbers == manifest.expected_page_numbers
            and review.pages_examined == manifest.expected_page_numbers
        )

    # ---------- server-derived missingness ----------

    def _current_missingness_reasons(self, item_id: str, claim: str) -> List[str]:
        source = self.current_source(item_id)
        if source is None:
            return ["NO_TRUSTED_SOURCE"]

        reasons: List[str] = []
        manifest = source.extraction_manifest
        if not manifest or not manifest.declared_text_surface_complete:
            reasons.append("DECLARED_TEXT_SURFACE_INCOMPLETE")

        review = self.get_current_document_review(item_id, claim)
        if review is None or not self.review_is_current(review.review_id):
            reasons.append("NO_CURRENT_PROTOCOL_COMPLETE_DOCUMENT_REVIEW")

        return sorted(set(reasons))

    def create_missingness_record(
        self, item_id: str, claim: str
    ) -> Optional[MissingnessRecord]:
        canonical_claim = canonicalize_claim(claim)
        reasons = self._current_missingness_reasons(item_id, canonical_claim)
        if not reasons:
            return None

        source = self.current_source(item_id)
        review_candidate = self.get_current_document_review(item_id, canonical_claim)
        review = (
            review_candidate
            if review_candidate is not None and self.review_is_current(review_candidate.review_id)
            else None
        )
        manifest = source.extraction_manifest if source else None
        claim_hash = _claim_hash(canonical_claim)
        snapshot = {
            "item_id": item_id,
            "claim_hash": claim_hash,
            "source_id": source.source_id if source else None,
            "source_revision": source.revision if source else None,
            "source_text_hash": source.text_sha256 if source else None,
            "extraction_manifest_hash": (
                manifest.extraction_manifest_hash if manifest else None
            ),
            "current_review_id": review.review_id if review else None,
            "reason_codes": reasons,
        }
        snapshot_hash = _sha256_text(
            json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        )
        missingness_id = "MIS_" + _sha256_text(
            f"{item_id}|{claim_hash}|{snapshot_hash}"
        )[:20]

        # Artifact identity is immutable: recreating the same declared missingness
        # situation returns the exact previously registered record instead of
        # overwriting it with a fresh timestamp or other mutable metadata.
        existing = self._missingness_registry.get(missingness_id)
        if existing is not None:
            return existing

        record = MissingnessRecord(
            missingness_id=missingness_id,
            item_id=item_id,
            claim=canonical_claim,
            claim_hash=claim_hash,
            source_id=source.source_id if source else None,
            source_revision=source.revision if source else None,
            source_text_hash=source.text_sha256 if source else None,
            extraction_manifest_hash=(
                manifest.extraction_manifest_hash if manifest else None
            ),
            current_review_id=review.review_id if review else None,
            reason_codes=reasons,
            evidence_surface_snapshot_hash=snapshot_hash,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        self._missingness_registry[missingness_id] = record
        self._persist()
        return record

    def get_missingness(self, missingness_id: str) -> Optional[MissingnessRecord]:
        return self._missingness_registry.get(missingness_id)

    def missingness_is_current(self, missingness_id: str) -> bool:
        record = self.get_missingness(missingness_id)
        if record is None:
            return False

        reasons = self._current_missingness_reasons(record.item_id, record.claim)
        if reasons != record.reason_codes:
            return False

        source = self.current_source(record.item_id)
        review_candidate = self.get_current_document_review(record.item_id, record.claim)
        review = (
            review_candidate
            if review_candidate is not None and self.review_is_current(review_candidate.review_id)
            else None
        )
        manifest = source.extraction_manifest if source else None
        snapshot = {
            "item_id": record.item_id,
            "claim_hash": record.claim_hash,
            "source_id": source.source_id if source else None,
            "source_revision": source.revision if source else None,
            "source_text_hash": source.text_sha256 if source else None,
            "extraction_manifest_hash": (
                manifest.extraction_manifest_hash if manifest else None
            ),
            "current_review_id": review.review_id if review else None,
            "reason_codes": reasons,
        }
        current_snapshot_hash = _sha256_text(
            json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        )
        return current_snapshot_hash == record.evidence_surface_snapshot_hash

    # ---------- audit log ----------

    def record_assessment(
        self,
        proposal: EvidenceAssessmentProposal,
        result: AdmissibilityResult,
    ) -> AssessmentRecord:
        record = AssessmentRecord(
            assessment_id="AS_" + uuid4().hex[:20],
            created_at=datetime.now(timezone.utc).isoformat(),
            proposal=proposal,
            result=result,
        )
        self._assessments.append(record)
        self._persist()
        return record

    def all_assessments(self) -> List[AssessmentRecord]:
        return list(self._assessments)

    def assessments_for_collection(self, collection_id: str) -> List[AssessmentRecord]:
        if not self.collection_exists(collection_id):
            raise ValueError(f"Unknown current collection_id: {collection_id}")
        allowed = self.items_in_collection(collection_id)
        return [r for r in self._assessments if r.proposal.item_id in allowed]

    def provenance_valid_for_record(self, record: AssessmentRecord) -> bool:
        status = record.proposal.proposed_status
        item_id = record.proposal.item_id

        if status in {
            EpistemicStatus.SUPPORTED,
            EpistemicStatus.PARTIALLY_SUPPORTED,
            EpistemicStatus.CONTRADICTED,
        }:
            return self.evidence_ids_all_current(
                record.result.evidence_ids or record.proposal.evidence_ids,
                item_id=item_id,
            )

        if status == EpistemicStatus.NOT_SUPPORTED:
            bound_review_ids = [
                artifact_id
                for artifact_id in record.result.supporting_artifact_ids
                if artifact_id.startswith("REV_")
            ]
            return bool(
                bound_review_ids
                and all(self.review_is_current(review_id) for review_id in bound_review_ids)
            )

        if status == EpistemicStatus.NON_EVALUABLE:
            bound_missingness_ids = [
                artifact_id
                for artifact_id in record.result.supporting_artifact_ids
                if artifact_id.startswith("MIS_")
            ]
            return bool(
                bound_missingness_ids
                and all(
                    self.missingness_is_current(missingness_id)
                    for missingness_id in bound_missingness_ids
                )
            )

        return False
