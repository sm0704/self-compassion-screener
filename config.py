"""Per-app labels and model for the self-compassion full-text decision review.

Only this file and prompt.py differ between the two screeners; streamlit_app.py is
identical. Edit the text below to change what end users see.
"""

APP_TITLE = "Self-Compassion Full-Text Decision Review"
APP_SUBTITLE = (
    "Method-section (Participants & Measures) eligibility check for the systematic "
    "review on self-compassion and academic functioning in students."
)
PAGE_ICON = "💚"
MODEL = "gemini-3-flash-preview"
INPUT_PLACEHOLDER = "Paste the paper's Participants and Measures (Method) section here…"

INTRO = """
**How to use**

1. Copy the paper's **Method** section — specifically the **Participants** (sample) and
   **Measures** subsections.
2. Paste them into the box and press Enter.
3. You'll get an **INCLUDE / EXCLUDE / MAYBE** decision with a confidence level, a short
   summary, a per-criterion checklist, and notes naming the scales.

This is the **full-text** stage, so it is strict — it checks three things: the sample
are **students**, self-compassion uses **Neff's (2003) full scale (all subscales)**, and
there is an **academic-specific measure** that can be separated from other items. If the
Method text doesn't say enough to decide, it returns MAYBE and lists what's missing.
"""

EXAMPLE = """METHOD
Participants: 320 undergraduate students at a public university (mean age 20.1 years).
Measures: Self-compassion was assessed with the 26-item Self-Compassion Scale (SCS; Neff, 2003), using a total score across all six subscales. Academic burnout was assessed with the Maslach Burnout Inventory–General Survey for Students (MBI-GS-S)."""
