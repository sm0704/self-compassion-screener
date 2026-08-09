"""Two-pass PDF extraction against the Gemini API.

Gemini reads PDFs natively as pages, which means it sees tables and figures that carry
no text layer — the exact content that defeats text-search-based extraction. Both passes
get the same PDF; pass 2 additionally receives pass 1's inventory.

Used by both the Streamlit app and the ADK agent's CLI-style entry point.
"""

from __future__ import annotations

import io
import json
import time
from dataclasses import dataclass, field
from typing import Callable, Optional

from google import genai
from google.genai import types

from .prompt import EXTRACTION_INSTRUCTION, INVENTORY_INSTRUCTION
from .schema import ExtractionRecord, Inventory

# Requests cap at 20MB total; stay well under it before switching to the Files API.
INLINE_LIMIT_BYTES = 15 * 1024 * 1024

# Files API processing poll settings.
_FILE_POLL_SECONDS = 1.5
_FILE_POLL_TIMEOUT = 180

DEFAULT_MODEL = "gemini-3.1-pro-preview"


class ExtractionError(RuntimeError):
    """Raised when a pass fails in a way the caller should surface to the reviewer."""


@dataclass
class ExtractionResult:
    inventory: Inventory
    record: ExtractionRecord
    model: str
    seconds: float
    inventory_tokens: Optional[int] = None
    extraction_tokens: Optional[int] = None
    warnings: list[str] = field(default_factory=list)

    @property
    def total_tokens(self) -> Optional[int]:
        if self.inventory_tokens is None and self.extraction_tokens is None:
            return None
        return (self.inventory_tokens or 0) + (self.extraction_tokens or 0)

    @property
    def effect_count(self) -> int:
        return sum(len(o.effects) for o in self.record.outcomes)


def build_client(api_key: str) -> genai.Client:
    """AI Studio client.

    vertexai=False is explicit so an ambient GOOGLE_GENAI_USE_VERTEXAI or
    GOOGLE_CLOUD_PROJECT in the host environment cannot silently reroute us to Vertex,
    which rejects AI Studio keys.
    """
    return genai.Client(api_key=api_key, vertexai=False)


def _upload_pdf(client: genai.Client, pdf_bytes: bytes, filename: str):
    """Upload via the Files API and wait for processing to finish."""
    handle = client.files.upload(
        file=io.BytesIO(pdf_bytes),
        config=types.UploadFileConfig(
            mime_type="application/pdf",
            display_name=filename,
        ),
    )
    deadline = time.monotonic() + _FILE_POLL_TIMEOUT
    while getattr(handle.state, "name", str(handle.state)) == "PROCESSING":
        if time.monotonic() > deadline:
            raise ExtractionError(
                f"Gemini took longer than {_FILE_POLL_TIMEOUT}s to process the PDF."
            )
        time.sleep(_FILE_POLL_SECONDS)
        handle = client.files.get(name=handle.name)

    if getattr(handle.state, "name", str(handle.state)) == "FAILED":
        raise ExtractionError("Gemini could not process this PDF. It may be corrupt.")
    return handle


def _pdf_part(client: genai.Client, pdf_bytes: bytes, filename: str):
    """Return (part, uploaded_handle_or_None) for the PDF."""
    if len(pdf_bytes) <= INLINE_LIMIT_BYTES:
        return (
            types.Part.from_bytes(data=pdf_bytes, mime_type="application/pdf"),
            None,
        )
    handle = _upload_pdf(client, pdf_bytes, filename)
    return (
        types.Part.from_uri(file_uri=handle.uri, mime_type=handle.mime_type),
        handle,
    )


def _usage(response) -> Optional[int]:
    meta = getattr(response, "usage_metadata", None)
    return getattr(meta, "total_token_count", None) if meta else None


def _call(
    client: genai.Client,
    model: str,
    parts: list,
    schema,
    temperature: Optional[float],
    attempts: int = 3,
):
    """One structured-output call, with retries on transient failures."""
    last_error: Optional[Exception] = None
    for attempt in range(attempts):
        try:
            # temperature is left unset by default. Pinning it to 0 on a reasoning-tier
            # model can degrade quality rather than improve determinism, and the
            # response schema already constrains the shape of the answer.
            config_kwargs = {
                "response_mime_type": "application/json",
                "response_schema": schema,
            }
            if temperature is not None:
                config_kwargs["temperature"] = temperature

            response = client.models.generate_content(
                model=model,
                contents=[types.Content(role="user", parts=parts)],
                config=types.GenerateContentConfig(**config_kwargs),
            )
            parsed = getattr(response, "parsed", None)
            if parsed is None:
                # The SDK could not coerce the reply; try the raw text ourselves so a
                # single malformed field doesn't lose the whole run.
                raw = (getattr(response, "text", "") or "").strip()
                if not raw:
                    raise ExtractionError("The model returned an empty response.")
                parsed = schema.model_validate(json.loads(raw))
            return parsed, _usage(response)
        except Exception as exc:  # noqa: BLE001 — retry anything transient, then surface
            last_error = exc
            if attempt < attempts - 1:
                time.sleep(2 * (attempt + 1))
    raise ExtractionError(f"Extraction call failed after {attempts} attempts: {last_error}")


def extract(
    pdf_bytes: bytes,
    filename: str,
    api_key: str,
    model: str = DEFAULT_MODEL,
    temperature: Optional[float] = None,
    progress: Optional[Callable[[str], None]] = None,
) -> ExtractionResult:
    """Run both passes over one article PDF and return the reviewable record.

    `progress` is called with a short status string before each pass so a UI can show
    where it is; extraction of a long paper takes a while.
    """
    if not pdf_bytes:
        raise ExtractionError("No PDF content was provided.")

    started = time.monotonic()
    client = build_client(api_key)
    warnings: list[str] = []

    part, handle = _pdf_part(client, pdf_bytes, filename)
    if handle is not None:
        warnings.append("Large PDF — uploaded via the Files API.")

    try:
        if progress:
            progress("Pass 1 of 2 — reading the article and enumerating what's in it…")
        inventory, inv_tokens = _call(
            client,
            model,
            [part, types.Part.from_text(text=INVENTORY_INSTRUCTION)],
            Inventory,
            temperature,
        )

        if progress:
            n = len(inventory.candidate_effects)
            progress(
                f"Pass 2 of 2 — applying the priority ladder to {n} candidate "
                f"effect{'s' if n != 1 else ''}…"
            )
        pass_two_prompt = (
            EXTRACTION_INSTRUCTION
            + json.dumps(inventory.model_dump(), indent=2, ensure_ascii=False)
        )
        record, ext_tokens = _call(
            client,
            model,
            [part, types.Part.from_text(text=pass_two_prompt)],
            ExtractionRecord,
            temperature,
        )
    finally:
        if handle is not None:
            try:
                client.files.delete(name=handle.name)
            except Exception:  # noqa: BLE001 — cleanup is best-effort; files expire anyway
                pass

    # Cross-check the two passes so silent drops surface as a warning rather than a
    # quietly short record.
    extracted = sum(len(o.effects) for o in record.outcomes)
    accounted = extracted + len(record.dropped_effects)
    candidates = len(inventory.candidate_effects)
    if candidates and accounted < candidates:
        warnings.append(
            f"Pass 1 found {candidates} candidate effect(s); pass 2 accounted for "
            f"{accounted} ({extracted} extracted, {len(record.dropped_effects)} dropped). "
            "Check the inventory for anything unexplained."
        )
    if not record.outcomes:
        warnings.append(
            "No academic-functioning outcomes were extracted. Check the rejected "
            "outcomes list — this may be correct, or the paper may not belong here."
        )

    return ExtractionResult(
        inventory=inventory,
        record=record,
        model=model,
        seconds=time.monotonic() - started,
        inventory_tokens=inv_tokens,
        extraction_tokens=ext_tokens,
        warnings=warnings,
    )
