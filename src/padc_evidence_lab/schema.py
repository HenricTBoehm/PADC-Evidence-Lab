from __future__ import annotations

from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from .normalization import canonicalize_claim


class EpistemicStatus(str, Enum):
    SUPPORTED = "S"
    PARTIALLY_SUPPORTED = "P"
    NOT_SUPPORTED = "NS"
    CONTRADICTED = "C"
    NON_EVALUABLE = "NE"


class AssessmentStage(str, Enum):
    PROPOSED = "PROPOSED"
    ADMISSIBLE = "ADMISSIBLE"
    REJECTED = "REJECTED"
    ADJUDICATED = "ADJUDICATED"


class SurfaceType(str, Enum):
    PAGE_INDEXED_TEXT = "PAGE_INDEXED_TEXT"


class ExtractionManifest(BaseModel):
    """Trusted declaration of the text surface available to the evidence engine.

    Completeness is intentionally scoped to PAGE_INDEXED_TEXT. It does not imply
    semantic exhaustion of images, table structure, embedded files, or any other
    excluded modality.
    """

    model_config = ConfigDict(frozen=True)

    surface_type: SurfaceType = SurfaceType.PAGE_INDEXED_TEXT
    expected_page_count: Optional[int] = Field(default=None, ge=1)
    expected_page_numbers: List[int] = Field(default_factory=list)
    extracted_page_numbers: List[int] = Field(default_factory=list)
    missing_page_numbers: List[int] = Field(default_factory=list)
    unexpected_page_numbers: List[int] = Field(default_factory=list)
    extraction_complete: bool = False
    declared_text_surface_complete: bool = False
    excluded_modalities: List[str] = Field(
        default_factory=lambda: ["IMAGES", "TABLE_STRUCTURE", "EMBEDDED_FILES"]
    )
    extraction_method: str = "trusted_page_json_v2"
    extraction_version: str = "0.1.1"
    extraction_manifest_hash: str


class SourceRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    source_id: str
    item_id: str
    title: str
    revision: int = Field(ge=1)
    text_sha256: str
    artifact_sha256: Optional[str] = None
    pages: Dict[int, str]
    collection_ids: List[str] = Field(default_factory=list)
    extraction_manifest: Optional[ExtractionManifest] = None


class SourceSummary(BaseModel):
    item_id: str
    source_id: str
    title: str
    revision: int
    pages_total: int
    pages_ingested: int
    expected_page_count: Optional[int] = None
    expected_page_numbers: List[int] = Field(default_factory=list)
    missing_page_numbers: List[int] = Field(default_factory=list)
    declared_text_surface_complete: bool = False
    extraction_manifest_hash: Optional[str] = None
    text_sha256: str
    artifact_sha256: Optional[str] = None
    collection_ids: List[str] = Field(default_factory=list)


class EvidenceObject(BaseModel):
    model_config = ConfigDict(frozen=True)

    evidence_id: str = Field(description="Server-derived immutable ID")
    item_id: str
    source_id: str
    source_revision: int = Field(ge=1)
    page_number: int = Field(gt=0)
    verbatim_excerpt: str = Field(min_length=1)
    source_text_hash: str
    page_hash: str
    excerpt_hash: str
    char_start: int = Field(ge=0)
    char_end: int = Field(gt=0)
    extraction_method: str = "server_page_search_v1"


class DocumentReview(BaseModel):
    model_config = ConfigDict(frozen=True)

    review_id: str
    item_id: str
    claim: str
    claim_hash: str
    source_id: str
    source_revision: int = Field(ge=1)
    source_text_hash: str

    # pages_total remains for v0.1.0 compatibility and means ingested text pages,
    # not independently established document length.
    pages_total: int = Field(ge=1)
    expected_page_count: Optional[int] = None
    expected_page_numbers: List[int] = Field(default_factory=list)
    pages_examined: List[int] = Field(default_factory=list)
    surface_type: SurfaceType = SurfaceType.PAGE_INDEXED_TEXT
    extraction_manifest_hash: Optional[str] = None
    declared_text_surface_complete: bool = False

    search_terms: List[str] = Field(default_factory=list)
    declared_semantic_queries_not_executed: List[str] = Field(default_factory=list)
    semantic_search_executed: bool = False
    semantic_search_adapter: Optional[str] = None

    review_contract_hash: str = ""
    executed_review_trace_hash: str = ""
    protocol_name: str = "page_indexed_text_scan_v2"
    fulltext_available: bool = False
    protocol_complete: bool
    matched_evidence_ids: List[str] = Field(default_factory=list)


class MissingnessRecord(BaseModel):
    model_config = ConfigDict(frozen=True)

    missingness_id: str
    item_id: str
    claim: str
    claim_hash: str
    source_id: Optional[str] = None
    source_revision: Optional[int] = None
    source_text_hash: Optional[str] = None
    extraction_manifest_hash: Optional[str] = None
    current_review_id: Optional[str] = None
    reason_codes: List[str] = Field(default_factory=list)
    evidence_surface_snapshot_hash: str
    created_at: str


class EvidenceAssessmentProposal(BaseModel):
    item_id: str
    claim: str = Field(min_length=3)
    proposed_status: EpistemicStatus

    @field_validator("claim", mode="before")
    @classmethod
    def canonicalize_claim_field(cls, value):
        if isinstance(value, str):
            return canonicalize_claim(value)
        return value
    evidence_ids: List[str] = Field(default_factory=list)
    conditions: List[str] = Field(default_factory=list)
    model_reported_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class AdmissibilityResult(BaseModel):
    item_id: str
    claim: str
    proposed_status: EpistemicStatus
    assessment_stage: AssessmentStage
    structurally_admissible: bool
    guard_triggered: Optional[str] = None
    evidence_ids: List[str] = Field(default_factory=list)
    supporting_artifact_ids: List[str] = Field(default_factory=list)
    conditions: List[str] = Field(default_factory=list)
    justification: str
    model_reported_confidence: Optional[float] = None


class AssessmentRecord(BaseModel):
    assessment_id: str
    created_at: str
    proposal: EvidenceAssessmentProposal
    result: AdmissibilityResult


class EvidenceMatrixRow(BaseModel):
    assessment_id: str
    created_at: str
    item_id: str
    claim: str
    proposed_status: EpistemicStatus
    assessment_stage: AssessmentStage
    evidence_ids: List[str] = Field(default_factory=list)
    supporting_artifact_ids: List[str] = Field(default_factory=list)
    conditions: List[str] = Field(default_factory=list)
    guard_triggered: Optional[str] = None
    provenance_valid: bool
    structurally_admissible: bool
    adjudicated_status: Optional[EpistemicStatus] = None


class EvidenceMatrixResult(BaseModel):
    collection_id: str
    total_assessments: int
    stage_counts: Dict[str, int]
    rows: List[EvidenceMatrixRow]
