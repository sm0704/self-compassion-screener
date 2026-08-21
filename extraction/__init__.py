"""Full-text data extraction for the self-compassion / academic-functioning review.

Shared verbatim by the ADK agent (`extraction_agent/`) and the Streamlit app
(`webapp/`). The webapp keeps its own copy of this package because Streamlit Community
Cloud deploys from the `webapp/` repo root; run `./sync_webapp.sh` after editing here.
"""

from .engine import (
    DEFAULT_MODEL,
    MIN_TEXT_CHARS,
    ExtractionError,
    ExtractionResult,
    build_client,
    extract,
    extract_text,
)
from .schema import (
    DOMAIN_ORDER,
    FIELD_LABELS,
    Effect,
    Evidence,
    ExtractionRecord,
    Inventory,
    Outcome,
    ResultsRecord,
    StudyRecord,
    merge,
)

__all__ = [
    "DEFAULT_MODEL",
    "MIN_TEXT_CHARS",
    "DOMAIN_ORDER",
    "FIELD_LABELS",
    "Effect",
    "Evidence",
    "ExtractionError",
    "ExtractionRecord",
    "ExtractionResult",
    "Inventory",
    "Outcome",
    "ResultsRecord",
    "StudyRecord",
    "build_client",
    "extract",
    "extract_text",
    "merge",
]
