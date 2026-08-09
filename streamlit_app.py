"""Entry point for the self-compassion review tools.

Two stages of the same systematic review, behind one URL and one password:

  Data extraction  — upload an included article's PDF, review every Covidence domain
                     with per-field evidence, then transcribe into the form.
  Screening        — paste a Method section, get INCLUDE / EXCLUDE / MAYBE.

Extraction is the default page because that is the stage currently in progress; swap
the `default=True` below if screening becomes the active stage again.

What changes per app:
  - Labels / models:        config.py
  - Screening rules:        prompt.py            (a copy of ../screening_agent/prompt.py)
  - Extraction rules:       extraction/prompt.py (a copy of ../extraction/prompt.py)
  - Secrets:                GOOGLE_API_KEY + APP_PASSWORD, set in Streamlit "Secrets"
                            (or as environment variables for local testing).
"""

import streamlit as st

from common import require_password
from config import APP_NAME, EXTRACTION_ICON, PAGE_ICON

# Wide layout: the extraction review page needs the horizontal room for its domain
# tabs and evidence captions. Must be the first Streamlit call.
st.set_page_config(page_title=APP_NAME, page_icon=PAGE_ICON, layout="wide")

require_password(APP_NAME, PAGE_ICON)

# Imported after the gate so nothing renders to an unauthenticated visitor.
from views import extractor, screener  # noqa: E402

# url_path is explicit because both page bodies are called `render`, and Streamlit
# otherwise infers the same pathname for both and refuses to build the navigation.
st.navigation(
    [
        st.Page(
            extractor.render,
            title="Data extraction",
            icon=EXTRACTION_ICON,
            url_path="extraction",
            default=True,
        ),
        st.Page(
            screener.render,
            title="Screening",
            icon=PAGE_ICON,
            url_path="screening",
        ),
    ]
).run()
