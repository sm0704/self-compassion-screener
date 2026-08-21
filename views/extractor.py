"""Extraction view — upload an article PDF, review every Covidence domain.

The layout deliberately mirrors the Covidence extraction form's domain rail
(Identification, Methods, Population, Interventions, Outcomes, Results data) so that
transcribing from this page into the form is a straight top-to-bottom copy.

Every value sits in a code block, which Streamlit renders with a one-click copy button —
that is the paste-into-Covidence affordance. Underneath each value is its page reference
and supporting quote, so a field can be verified without reopening the paper.
"""

import hashlib
from datetime import datetime

import streamlit as st

from common import require_api_key
from config import (
    EXTRACTION_ICON,
    EXTRACTION_INTRO,
    EXTRACTION_MODEL,
    EXTRACTION_MODEL_CHOICES,
    EXTRACTION_SUBTITLE,
    EXTRACTION_TEXT_HELP,
    EXTRACTION_TITLE,
)
from extraction import MIN_TEXT_CHARS, ExtractionError, extract, extract_text
from extraction.schema import FIELD_LABELS, Evidence

_CONFIDENCE = {
    "high": ("🟢", "stated explicitly"),
    "medium": ("🟡", "needed light interpretation"),
    "low": ("🔴", "ambiguous — check this one"),
    "absent": ("⚪", "not reported in the paper"),
}

_FLAG = {
    "uncertain": ("🔴", "Needs checking"),
    "conflict": ("⚠️", "Conflicting values"),
    "unreadable": ("⚫", "Could not be read"),
    "blank": ("🟡", "Not reported"),
    "extra": ("🟢", "Extra data found"),
}
_FLAG_ORDER = ["conflict", "unreadable", "uncertain", "blank", "extra"]


# ───────────────────────────── small renderers ─────────────────────────────


def _code(value: str) -> None:
    """Value in a copy-button code block, wrapping when the Streamlit build allows."""
    try:
        st.code(value, language=None, wrap_lines=True)
    except TypeError:  # older Streamlit without wrap_lines
        st.code(value, language=None)


def _field(label: str, ev: Evidence) -> None:
    icon, meaning = _CONFIDENCE.get(ev.confidence, ("⚪", ev.confidence))
    st.markdown(f"**{label}** &nbsp;{icon}", unsafe_allow_html=True)

    value = (ev.value or "").strip()
    if value:
        _code(value)
    else:
        st.markdown(":gray[— not reported —]")

    meta = []
    if ev.page:
        meta.append(f"**{ev.page}**")
    if ev.quote:
        meta.append(f'"{ev.quote}"')
    if ev.note:
        meta.append(f"_{ev.note}_")
    if not value or ev.confidence in ("low", "absent"):
        meta.append(f"_{meaning}_")
    if meta:
        st.caption(" · ".join(meta))


def _evidence_fields(obj, skip: tuple = ()) -> None:
    """Render every Evidence field of a model in declaration order."""
    for name, val in obj:
        if name in skip or not isinstance(val, Evidence):
            continue
        _field(FIELD_LABELS.get(name, name.replace("_", " ").capitalize()), val)


def _render_effect(effect, index: int) -> None:
    st.markdown(f"##### Effect {index}")
    st.caption(
        f"Priority ladder rung **{effect.ladder_rung}** — {effect.ladder_rationale}"
    )
    _evidence_fields(effect, skip=("supplemental",))

    supplemental = [(n, ev) for n, ev in effect.supplemental if (ev.value or "").strip()]
    if supplemental:
        with st.expander(f"Supplemental statistics ({len(supplemental)})"):
            for name, ev in supplemental:
                _field(FIELD_LABELS.get(name, name), ev)


# ───────────────────────────── result sections ─────────────────────────────


def _summary(result) -> None:
    record = result.record
    title = (record.identification.title.value or "").strip()
    citation = (record.identification.citation.value or "").strip()

    if title:
        st.subheader(title)
    if citation:
        st.caption(citation)

    needs_attention = sum(
        1 for f in record.flags if f.level in ("uncertain", "conflict", "unreadable")
    )
    cols = st.columns(4)
    cols[0].metric("Academic outcomes", len(record.outcomes))
    cols[1].metric("Effects extracted", result.effect_count)
    cols[2].metric("Needs checking", needs_attention)
    cols[3].metric("Extraction time", f"{result.seconds:.0f}s")

    footnote = f"Model: `{result.model}`"
    if result.source == "text":
        footnote += " · from pasted text"
    if result.total_tokens:
        footnote += f" · {result.total_tokens:,} tokens"
    st.caption(footnote)

    for warning in result.warnings:
        st.warning(warning, icon="⚠️")


def _flags(record) -> None:
    if not record.flags:
        st.success("No flags raised. Still worth spot-checking the Results data.", icon="✅")
        return

    by_level = {}
    for flag in record.flags:
        by_level.setdefault(flag.level, []).append(flag)

    priority = [lvl for lvl in _FLAG_ORDER if lvl in by_level]
    urgent = sum(len(by_level.get(l, [])) for l in ("conflict", "unreadable", "uncertain"))

    with st.expander(
        f"Flags — {len(record.flags)} total, {urgent} needing attention",
        expanded=urgent > 0,
    ):
        for level in priority:
            icon, label = _FLAG.get(level, ("•", level))
            st.markdown(f"**{icon} {label}**")
            for flag in by_level[level]:
                st.markdown(f"- `{flag.field}` — {flag.message}")


def _outcomes_tab(record) -> None:
    if not record.outcomes:
        st.warning(
            "No academic-functioning outcomes were extracted. Check **Review notes** for "
            "what was rejected — either the paper genuinely has none, or something was "
            "wrongly excluded.",
            icon="⚠️",
        )
        return

    st.info(
        f"**{len(record.outcomes)} academic variable"
        f"{'s' if len(record.outcomes) != 1 else ''}** → that many Outcomes entries in "
        "Covidence. Each card shows how many effects it holds, which is what the "
        "**Timepoints** control must be set to for that variable.",
        icon="📋",
    )

    for i, outcome in enumerate(record.outcomes, start=1):
        name = (outcome.academic_variable_name.value or f"Outcome {i}").strip()
        with st.container(border=True):
            st.markdown(f"### {i}. {name}")
            n = len(outcome.effects)
            st.caption(
                f"Timepoints / Extra Effects for this variable: **{n}** "
                f"({n} effect{'s' if n != 1 else ''} to enter under Results data)"
            )
            _evidence_fields(outcome, skip=("effects",))


def _results_tab(record) -> None:
    if not record.outcomes:
        st.markdown(":gray[No effects were extracted.]")
        return

    st.info(
        "Set each variable's **Timepoints** count in the Outcomes domain *before* "
        "filling these in — adding timepoints afterwards regenerates the Results slots.",
        icon="⚠️",
    )

    for i, outcome in enumerate(record.outcomes, start=1):
        name = (outcome.academic_variable_name.value or f"Outcome {i}").strip()
        st.markdown(f"### {i}. {name}")
        if not outcome.effects:
            st.markdown(":gray[No effects recorded for this variable.]")
            continue
        for j, effect in enumerate(outcome.effects, start=1):
            with st.container(border=True):
                _render_effect(effect, j)
        st.divider()


def _review_notes_tab(result) -> None:
    record = result.record

    st.markdown("#### Outcomes rejected as non-academic")
    if record.rejected_outcomes:
        st.caption(
            "Scan this list — a wrongly rejected outcome is the most likely way an "
            "effect goes missing."
        )
        for item in record.rejected_outcomes:
            st.markdown(f"- **{item.name}** — {item.reason}")
    else:
        st.markdown(":gray[None recorded.]")

    st.divider()
    st.markdown("#### Effects dropped by the priority ladder")
    if record.dropped_effects:
        st.caption(
            "Each of these was superseded by a higher-priority statistic for the same "
            "self-compassion × academic pair."
        )
        for item in record.dropped_effects:
            st.markdown(f"- {item.description} → superseded by **{item.superseded_by}**")
    else:
        st.markdown(":gray[None — no lower-priority statistics competed.]")

    st.divider()
    st.markdown("#### Reading coverage")
    cov = record.coverage
    st.markdown(f"- **Pages:** {cov.pages_total or '—'}")
    for label, items in (
        ("Sections read", cov.sections_read),
        ("Tables inspected", cov.tables_inspected),
        ("Figures inspected", cov.figures_inspected),
    ):
        st.markdown(f"- **{label}:** {', '.join(items) if items else '—'}")
    if cov.unreadable:
        st.error(
            "**Could not be read — check these by hand:** " + "; ".join(cov.unreadable),
            icon="⚫",
        )

    st.divider()
    with st.expander("Pass 1 inventory (everything found before ladder filtering)"):
        inv = result.inventory
        st.markdown(f"**Total self-compassion reported:** {'yes' if inv.total_sc_reported else 'no'}")
        st.markdown(f"**Self-compassion measure:** {inv.sc_measure_summary}")
        st.markdown(
            f"**Academic variables found:** {', '.join(inv.academic_variables) or '—'}"
        )
        st.markdown(f"**Candidate effects:** {len(inv.candidate_effects)}")
        for cand in inv.candidate_effects:
            st.markdown(
                f"- rung {cand.ladder_rung} · **{cand.academic_variable}** × "
                f"{cand.sc_variable} · {cand.statistic_type} = `{cand.reported_value}` "
                f"({cand.location})"
            )
        if inv.notes:
            st.markdown(f"**Notes:** {inv.notes}")


# ──────────────────────────────── the page ────────────────────────────────


def _run_extraction(*, digest: str, name: str, button_key: str, disabled: bool, run) -> None:
    """Extract button + status + error handling, shared by the PDF and text panes.

    `digest` fingerprints the input so the button can say whether this exact article has
    already been run; `run` takes a progress callback and returns an ExtractionResult.
    """
    already_done = st.session_state.get("extraction_digest") == digest
    label = "Re-run extraction" if already_done else "Extract"

    if not st.button(label, type="primary", key=button_key, disabled=disabled):
        return

    try:
        with st.status("Starting…", expanded=True) as status:
            result = run(lambda msg: st.write(msg))
            status.update(
                label=f"Done in {result.seconds:.0f}s", state="complete", expanded=False
            )
        st.session_state.extraction_result = result
        st.session_state.extraction_digest = digest
        st.session_state.extraction_filename = name
        st.rerun()
    except ExtractionError as exc:
        st.error(f"Extraction failed: {exc}", icon="🚫")
    except Exception as exc:  # noqa: BLE001 — keep the app alive, show the cause
        st.error(
            "Something went wrong talking to the model. Please try again.\n\n"
            f"_Technical detail: {exc}_",
            icon="🚫",
        )


def render() -> None:
    api_key = require_api_key()

    st.title(f"{EXTRACTION_ICON} {EXTRACTION_TITLE}")
    st.caption(EXTRACTION_SUBTITLE)

    with st.sidebar:
        st.markdown(f"### {EXTRACTION_ICON} {EXTRACTION_TITLE}")
        st.markdown(EXTRACTION_INTRO)
        st.divider()
        default_index = (
            EXTRACTION_MODEL_CHOICES.index(EXTRACTION_MODEL)
            if EXTRACTION_MODEL in EXTRACTION_MODEL_CHOICES
            else 0
        )
        model = st.selectbox(
            "Model",
            EXTRACTION_MODEL_CHOICES,
            index=default_index,
            help=(
                "Pro tiers read dense tables more reliably. Switch here to compare runs "
                "on the same article."
            ),
        )
        if st.session_state.get("extraction_result") and st.button(
            "🧹 Clear result", use_container_width=True
        ):
            for key in ("extraction_result", "extraction_digest", "extraction_filename"):
                st.session_state.pop(key, None)
            st.rerun()

    pdf_tab, text_tab = st.tabs(["📄 Upload PDF", "📝 Paste text"])

    with pdf_tab:
        uploaded = st.file_uploader(
            "Article PDF (downloaded from Covidence)",
            type=["pdf"],
            help="The full text, not just the abstract. Theses are fine — they take longer.",
        )
        if uploaded is not None:
            pdf_bytes = uploaded.getvalue()
            _run_extraction(
                digest=hashlib.sha256(pdf_bytes).hexdigest(),
                name=uploaded.name,
                button_key="extract_pdf",
                disabled=not pdf_bytes,
                run=lambda on_progress: extract(
                    pdf_bytes=pdf_bytes,
                    filename=uploaded.name,
                    api_key=api_key,
                    model=model,
                    progress=on_progress,
                ),
            )

    with text_tab:
        st.caption(EXTRACTION_TEXT_HELP)
        pasted = st.text_area(
            "Article text",
            height=260,
            placeholder=(
                "Paste the whole article — Method and Results in particular, including "
                "every table you can copy out."
            ),
            help=(
                "Second choice. The model cannot see figures or image-only tables here, "
                "and pasted tables lose their column alignment — upload the PDF when you "
                "can."
            ),
        )
        text = (pasted or "").strip()
        if text:
            st.caption(f"{len(text):,} characters · {len(text.split()):,} words")
            if len(text) < MIN_TEXT_CHARS:
                st.warning(
                    f"That is shorter than {MIN_TEXT_CHARS:,} characters — an abstract, "
                    "not a full text. Paste the whole article.",
                    icon="⚠️",
                )
        _run_extraction(
            digest=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            name="pasted_text",
            button_key="extract_text",
            disabled=len(text) < MIN_TEXT_CHARS,
            run=lambda on_progress: extract_text(
                article_text=text,
                api_key=api_key,
                model=model,
                progress=on_progress,
            ),
        )

    result = st.session_state.get("extraction_result")
    if result is None:
        st.info(
            "Upload a PDF to begin — or paste the article's text if no PDF is available. "
            "Extraction reads the whole article (from a PDF, that includes tables and "
            "figures carrying no text layer) and usually takes a minute or two.",
            icon="📄",
        )
        return

    record = result.record
    st.divider()
    _summary(result)
    _flags(record)

    tabs = st.tabs(
        [
            "Identification",
            "Methods",
            "Population",
            "Interventions",
            "Outcomes",
            "Results data",
            "Review notes",
        ]
    )
    with tabs[0]:
        _evidence_fields(record.identification)
    with tabs[1]:
        _evidence_fields(record.methods)
        st.caption(
            "⚠️ *Number of timepoints* here means real measurement waves — not the "
            "Outcomes **Timepoints** control, which means extra effects."
        )
    with tabs[2]:
        _evidence_fields(record.population)
    with tabs[3]:
        st.caption(
            "The Covidence **Interventions** domain records the *self-compassion "
            "measure*. The program's name and duration belong under **Methods**."
        )
        _evidence_fields(record.sc_measure)
    with tabs[4]:
        _outcomes_tab(record)
    with tabs[5]:
        _results_tab(record)
    with tabs[6]:
        _review_notes_tab(result)

    st.divider()
    stem = (st.session_state.get("extraction_filename") or "extraction").rsplit(".", 1)[0]
    st.download_button(
        "⬇️ Download JSON",
        data=record.model_dump_json(indent=2),
        file_name=f"{stem}_{datetime.now():%Y%m%d_%H%M}.json",
        mime="application/json",
        help="The full record, for your own archive or to diff against another run.",
    )
