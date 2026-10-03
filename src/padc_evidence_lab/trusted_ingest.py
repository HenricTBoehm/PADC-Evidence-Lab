from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from .evidence_store import EvidenceStore


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_pages(path: Path) -> dict[int, str]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("pages JSON must be an object mapping page numbers to strings")

    pages: dict[int, str] = {}
    for key, value in raw.items():
        page = int(key)
        if page <= 0:
            raise ValueError(f"Invalid page number: {page}")
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"Page {page} must contain non-empty text")
        pages[page] = value
    return pages


def parse_expected_pages(value: str | None) -> list[int] | None:
    if not value:
        return None
    pages = sorted({int(part.strip()) for part in value.split(",") if part.strip()})
    if not pages or any(page <= 0 for page in pages):
        raise ValueError("--expected-pages must contain positive comma-separated integers")
    return pages


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Trusted out-of-band source ingestion for PADC Evidence Lab."
    )
    parser.add_argument("--state", required=True, help="Path to persistent JSON state file")
    parser.add_argument("--item-id", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--pages-json", required=True)
    parser.add_argument(
        "--collection",
        action="append",
        default=[],
        help="Collection ID; repeat for multiple collections",
    )
    parser.add_argument(
        "--artifact",
        default=None,
        help="Optional path to original artifact (e.g. PDF) for SHA-256 recording",
    )
    parser.add_argument(
        "--expected-page-count",
        type=int,
        default=None,
        help="Trusted expected contiguous page count (1..N) for PAGE_INDEXED_TEXT.",
    )
    parser.add_argument(
        "--expected-pages",
        default=None,
        help="Trusted expected page numbers, comma-separated. Use instead of count for non-contiguous surfaces.",
    )
    parser.add_argument(
        "--extraction-method",
        default="trusted_page_json_v2",
    )
    parser.add_argument(
        "--extraction-version",
        default="0.1.1",
    )
    parser.add_argument(
        "--excluded-modality",
        action="append",
        default=[],
        help="Modality explicitly excluded from the declared text surface; repeat as needed.",
    )
    args = parser.parse_args()

    pages_path = Path(args.pages_json)
    pages = load_pages(pages_path)
    expected_pages = parse_expected_pages(args.expected_pages)

    artifact_sha256 = None
    if args.artifact:
        artifact_sha256 = sha256_file(Path(args.artifact))

    store = EvidenceStore(args.state)
    source = store.ingest_source(
        item_id=args.item_id,
        title=args.title,
        pages=pages,
        collection_ids=args.collection,
        artifact_sha256=artifact_sha256,
        expected_page_count=args.expected_page_count,
        expected_page_numbers=expected_pages,
        extraction_method=args.extraction_method,
        extraction_version=args.extraction_version,
        excluded_modalities=(args.excluded_modality or None),
    )

    manifest = source.extraction_manifest
    print(
        json.dumps(
            {
                "source_id": source.source_id,
                "item_id": source.item_id,
                "revision": source.revision,
                "pages_ingested": len(source.pages),
                "expected_page_count": manifest.expected_page_count if manifest else None,
                "expected_page_numbers": manifest.expected_page_numbers if manifest else [],
                "missing_page_numbers": manifest.missing_page_numbers if manifest else [],
                "declared_text_surface_complete": (
                    manifest.declared_text_surface_complete if manifest else False
                ),
                "surface_type": manifest.surface_type.value if manifest else None,
                "excluded_modalities": manifest.excluded_modalities if manifest else [],
                "extraction_manifest_hash": (
                    manifest.extraction_manifest_hash if manifest else None
                ),
                "text_sha256": source.text_sha256,
                "artifact_sha256": source.artifact_sha256,
                "collection_ids": source.collection_ids,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
