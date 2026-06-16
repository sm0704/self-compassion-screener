"""Per-app labels and model for the self-compassion screener.

Only this file and prompt.py differ between the two screeners; streamlit_app.py is
identical. Edit the text below to change what end users see.
"""

APP_TITLE = "Self-Compassion Article Screener"
APP_SUBTITLE = (
    "Title & abstract screening for the systematic review on self-compassion and "
    "academic functioning in students."
)
PAGE_ICON = "💚"
MODEL = "gemini-3-flash-preview"
INPUT_PLACEHOLDER = "Paste the article's title and abstract here…"

INTRO = """
**How to use**

1. Copy an article's **title** and **abstract**.
2. Paste them into the box and press Enter.
3. You'll get an **INCLUDE / EXCLUDE / MAYBE** decision with a confidence level, a
   short summary, a per-criterion checklist, and any notes.

The screener follows the review's *"include when unsure"* rule, so borderline papers
are kept in for later full-text review.
"""

EXAMPLE = """TITLE: The role of self-compassion in the academic stress model
ABSTRACT: This study investigated the effect of self-compassion on the relationships among academic demand, academic burnout, and depression in senior university students from five universities in South Korea (N = 154). Structural equation modeling and multi-group analysis were used."""
