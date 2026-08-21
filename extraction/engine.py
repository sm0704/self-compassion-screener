"""Three-pass PDF extraction against the Gemini API.

Gemini reads PDFs natively as pages, which means it sees tables and figures that carry
no text layer — the exact content that defeats text-search-based extraction. Every pass
gets the same article; passes 2 and 3 additionally receive pass 1's inventory.

`extract()` takes a PDF and is the path to prefer. `extract_text()` takes text pasted by
the reviewer, for the cases where no PDF can be had — a paywalled article read in the
browser, a publisher viewer that will not export. It runs the identical three passes on
a text part instead of a PDF part, with the prompts told what pasting loses: figures,
image-only tables, and the column grid of every table that survived as loose numbers.

  1. inventory  — read the whole paper and enumerate every candidate effect.
  2. study      — Identification, Methods, Population, the self-compassion measure.
  3. results    — the academic outcomes, their effects, and what was dropped.

Passes 2 and 3 are independent of each other and are split for a mechanical reason: the
full record is too large a response schema for the API to accept. See `schema.py`.

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

from .prompt import (
    PDF_SOURCE,
    TEXT_ARTICLE_HEADER,
    TEXT_SOURCE,
    Source,
    inventory_instruction,
    results_instruction,
    study_instruction,
)
from .schema import ExtractionRecord, Inventory, ResultsRecord, StudyRecord, merge

# Requests cap at 20MB total; stay well under it before switching to the Files API.
INLINE_LIMIT_BYTES = 15 * 1024 * 1024

# Below this, what was pasted cannot be a full text — it is an abstract, a page of a
# PDF viewer, or an empty clipboard. Extracting from it would produce a confident-looking
# record built on nothing, which is the one failure mode this tool must not have.
MIN_TEXT_CHARS = 1500

# Files API processing poll settings.
_FILE_POLL_SECONDS = 1.5
_FILE_POLL_TIMEOUT = 180

DEFAULT_MODEL = "gemini-3-flash-preview"


class ExtractionError(RuntimeError):
    """Raised when a pass fails in a way the caller should surface to the reviewer."""


@dataclass
class ExtractionResult:
    inventory: Inventory
    record: ExtractionRecord
    model: str
    seconds: float
    source: str = "pdf"  # "pdf" or "text" — what the reviewer gave us
    inventory_tokens: Optional[int] = None
    extraction_tokens: Optional[int] = None  # study pass + results pass
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


def _fatal_client_error(exc: Exception) -> Optional[str]:
    """Return an explanation if `exc` is a request-level rejection, else None.

    A 4xx other than 429 means the request itself is wrong — the same request will be
    wrong three seconds later, so retrying only delays the error and buries the cause.
    400 INVALID_ARGUMENT in particular is what the API returns for a response schema it
    considers too large, and it says nothing about the schema, so name that possibility.
    """
    code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
    if not isinstance(code, int) or code == 429 or not 400 <= code < 500:
        return None

    text = str(exc)
    if "API key not valid" in text or "API_KEY_INVALID" in text or code in (401, 403):
        return (
            f"Gemini rejected the credentials ({code}). Check GOOGLE_API_KEY — for the "
            f"deployed app that is Settings → Secrets. Full error: {text}"
        )
    if code == 404:
        return f"Model not available: {text}"
    # "Request contains an invalid argument." is all the API says when it will not take
    # a response schema — it names neither the schema nor the field.
    if code == 400 and "Request contains an invalid argument" in text:
        return (
            "Gemini rejected the request (400 INVALID_ARGUMENT) without saying why. The "
            "usual cause is a response schema it considers too large — run "
            f"`python -m extraction.schema` to see which one. Full error: {text}"
        )
    return f"Gemini rejected the request ({code}): {text}"


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
            fatal = _fatal_client_error(exc)
            if fatal:
                raise ExtractionError(fatal) from exc
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
    """Run all three passes over one article PDF and return the reviewable record.

    `progress` is called with a short status string before each pass so a UI can show
    where it is; extraction of a long paper takes a while.
    """
    if not pdf_bytes:
        raise ExtractionError("No PDF content was provided.")

    client = build_client(api_key)
    warnings: list[str] = []
    part, handle = _pdf_part(client, pdf_bytes, filename)
    if handle is not None:
        warnings.append("Large PDF — uploaded via the Files API.")

    try:
        return _run(
            client,
            part,
            PDF_SOURCE,
            "pdf",
            model=model,
            temperature=temperature,
            progress=progress,
            warnings=warnings,
        )
    finally:
        if handle is not None:
            try:
                client.files.delete(name=handle.name)
            except Exception:  # noqa: BLE001 — cleanup is best-effort; files expire anyway
                pass


def extract_text(
    article_text: str,
    api_key: str,
    model: str = DEFAULT_MODEL,
    temperature: Optional[float] = None,
    progress: Optional[Callable[[str], None]] = None,
) -> ExtractionResult:
    """Same three passes, over text the reviewer pasted instead of a PDF.

    Use only when a PDF cannot be had. Pasted text loses figures, image-only tables, and
    the column alignment of the tables that do survive — which is where most effects
    live. The prompts say so, and the record comes back with a standing warning, because
    a value that is merely absent from the paste must not read as absent from the paper.
    """
    text = (article_text or "").strip()
    if not text:
        raise ExtractionError("No article text was provided.")
    if len(text) < MIN_TEXT_CHARS:
        raise ExtractionError(
            f"Only {len(text):,} characters of text were provided — too short to be a "
            "full article (the Method and Results sections alone run longer than "
            f"{MIN_TEXT_CHARS:,}). Paste the whole article, or upload the PDF."
        )

    client = build_client(api_key)
    return _run(
        client,
        types.Part.from_text(text=TEXT_ARTICLE_HEADER + text),
        TEXT_SOURCE,
        "text",
        model=model,
        temperature=temperature,
        progress=progress,
        warnings=[
            "Extracted from pasted text, not a PDF. Figures and image-only tables were "
            "not available to the model, and pasted tables lose their column alignment — "
            "check every effect against the article itself, and treat a missing value as "
            "unconfirmed rather than absent."
        ],
    )


def _run(
    client: genai.Client,
    source_part,
    source: Source,
    source_kind: str,
    *,
    model: str,
    temperature: Optional[float],
    progress: Optional[Callable[[str], None]],
    warnings: list[str],
) -> ExtractionResult:
    """The three passes, over whichever kind of article part it is handed."""
    started = time.monotonic()

    if progress:
        progress("Pass 1 of 3 — reading the article and enumerating what's in it…")
    inventory, inv_tokens = _call(
        client,
        model,
        [source_part, types.Part.from_text(text=inventory_instruction(source))],
        Inventory,
        temperature,
    )

    # Both extraction passes read the same inventory; neither reads the other's output,
    # so the only thing they have to agree on is this text.
    inventory_json = json.dumps(inventory.model_dump(), indent=2, ensure_ascii=False)

    if progress:
        progress("Pass 2 of 3 — filling in the study-level domains…")
    study, study_tokens = _call(
        client,
        model,
        [source_part, types.Part.from_text(text=study_instruction(source) + inventory_json)],
        StudyRecord,
        temperature,
    )

    if progress:
        n = len(inventory.candidate_effects)
        progress(
            f"Pass 3 of 3 — applying the priority ladder to {n} candidate "
            f"effect{'s' if n != 1 else ''}…"
        )
    results, results_tokens = _call(
        client,
        model,
        [source_part, types.Part.from_text(text=results_instruction(source) + inventory_json)],
        ResultsRecord,
        temperature,
    )

    record = merge(study, results)
    ext_tokens = (
        None
        if study_tokens is None and results_tokens is None
        else (study_tokens or 0) + (results_tokens or 0)
    )

    # Cross-check the inventory against the results pass so silent drops surface as a
    # warning rather than a quietly short record.
    extracted = sum(len(o.effects) for o in record.outcomes)
    accounted = extracted + len(record.dropped_effects)
    candidates = len(inventory.candidate_effects)
    if candidates and accounted < candidates:
        warnings.append(
            f"Pass 1 found {candidates} candidate effect(s); pass 3 accounted for "
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
        source=source_kind,
        inventory_tokens=inv_tokens,
        extraction_tokens=ext_tokens,
        warnings=warnings,
    )
