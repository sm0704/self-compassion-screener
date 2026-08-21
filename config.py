"""Per-app labels and models.

Two tools live in this app, corresponding to two stages of the review:

  Screening  — paste a Method section, get INCLUDE / EXCLUDE / MAYBE.
               Rules live in prompt.py.
  Extraction — upload the full-text PDF, get all Covidence domains filled in with
               per-field evidence. Rules live in extraction/prompt.py.

Edit the text below to change what end users see.
"""

# ── shared ────────────────────────────────────────────────────────────────
APP_NAME = "Self-Compassion Review Tools"
PAGE_ICON = "💚"

# ── screening tool ────────────────────────────────────────────────────────
APP_TITLE = "Self-Compassion Full-Text Decision Review"
APP_SUBTITLE = (
    "Method-section (Participants & Measures) eligibility check for the systematic "
    "review on self-compassion and academic functioning in students."
)
MODEL = "gemini-3-flash-preview"
INPUT_PLACEHOLDER = "Paste the paper's Participants and Measures (Method) section here…"

INTRO = """
**How to use**

1. Copy the paper's **Method** section — specifically the **Participants** (sample) and
   **Measures** subsections.
2. Paste them into the box and press Enter.
3. You'll get an **INCLUDE / EXCLUDE / MAYBE** decision with a confidence level, a short
   summary, a per-criterion checklist, and notes.

This is the **full-text** stage, so it is strict — it checks three things: the sample
are **students**, self-compassion uses **Neff's (2003) full scale (all subscales)**, and
there is an **academic-specific measure** that can be separated from other items. If the
Method text doesn't say enough to decide, it returns MAYBE and lists what's missing.
"""

EXAMPLE = """METHOD
Participants: 320 undergraduate students at a public university (mean age 20.1 years).
Measures: Self-compassion was assessed with the 26-item Self-Compassion Scale (SCS; Neff, 2003), using a total score across all six subscales. Academic burnout was assessed with the Maslach Burnout Inventory–General Survey for Students (MBI-GS-S)."""


# ── extraction tool ───────────────────────────────────────────────────────
EXTRACTION_TITLE = "Full-Text Data Extraction"
EXTRACTION_ICON = "📋"
EXTRACTION_SUBTITLE = (
    "Upload an included article's PDF — or paste its text if no PDF is available — and "
    "get every Covidence domain filled in, with a page reference and supporting quote "
    "behind each value, ready to review and transcribe into the extraction form."
)

# Shown above the paste box. The point of the tab is that some articles can be read but
# not downloaded; the point of this caption is that using it costs you something.
EXTRACTION_TEXT_HELP = (
    "For articles you can read but not download. The model sees only what you paste — "
    "**no figures, and no table that was an image** — and copied tables usually lose "
    "their column alignment, so numbers can land under the wrong heading. Upload the "
    "PDF whenever you can, and check every effect here against the article."
)

# Roughly $0.03-0.05 per article, against $0.16-0.27 on gemini-3.1-pro-preview — and
# notably ~5x cheaper than gemini-3.6-flash, which is priced close to Pro.
#
# Not yet validated against a Pro run. The risk with a cheaper tier on this task is
# specific: misreading a cell in a dense correlation matrix, and marking every field
# "high" confidence so the flags panel stops being useful. Worth diffing against a Pro
# run on a paper that has both a correlation matrix and a regression table.
EXTRACTION_MODEL = "gemini-3-flash-preview"

# Offered in the sidebar so runs can be compared on the same article. Cheapest first.
# Every entry is checked against the live API — gemini-2.5-pro and gemini-3-pro-preview
# were listed here and both now 404 for this key, so picking them only produced an error.
EXTRACTION_MODEL_CHOICES = [
    "gemini-3-flash-preview",
    "gemini-3.6-flash",
    "gemini-3.1-pro-preview",
]

EXTRACTION_INTRO = """
**How to use**

1. Download the article's PDF from Covidence.
2. Upload it below and press **Extract**. No PDF? Use the **Paste text** tab instead —
   copy the whole article, Method and Results especially, tables included.
3. Review each domain. Every field shows its page reference and a supporting quote, so
   you can verify it without re-reading the paper.
4. Copy the values into the Covidence extraction form.

**Read the flags first.** 🔴 low-confidence and ⚪ not-reported fields are where your
attention is worth the most. The **Review notes** tab lists which outcomes were rejected
as non-academic and which effects were dropped in favour of a higher-priority statistic —
that's where a missed effect would show up.

Pasted text is the fallback, not the default: figures and image-only tables simply are
not there, so a value that is missing may be missing from your paste rather than from
the paper. The result banner says when a record came from text.

Nothing is submitted anywhere. This tool only reads what you give it; you enter the data
yourself.
"""
