from __future__ import annotations

import unicodedata


def canonicalize_claim(value: str) -> str:
    """Return the canonical claim form used for new artifact identity.

    v0.1.1.1 normalizes Unicode to NFC and collapses all runs of whitespace to a
    single ASCII space. The function is deliberately narrow: it normalizes
    representation, not meaning.
    """
    return " ".join(unicodedata.normalize("NFC", value).split())
