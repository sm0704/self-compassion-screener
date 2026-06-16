"""Streamlit chat front-end for the article-screening agent.

A thin web wrapper around the SAME screening prompt the Google ADK agent uses. It
calls Gemini directly via google-genai, so it needs no ADK and runs anywhere
Streamlit runs — including the free Streamlit Community Cloud.

What changes per app:
  - Labels / model:   config.py
  - Screening rules:  prompt.py   (a copy of ../screening_agent/prompt.py)
  - Secrets:          GOOGLE_API_KEY + APP_PASSWORD, set in Streamlit "Secrets"
                      (or as environment variables for local testing).

This file is intentionally identical across both screeners — only config.py and
prompt.py differ.
"""

import os

import streamlit as st
from google import genai
from google.genai import types

from config import (
    APP_TITLE,
    APP_SUBTITLE,
    PAGE_ICON,
    INPUT_PLACEHOLDER,
    MODEL,
    INTRO,
    EXAMPLE,
)
from prompt import SCREENING_INSTRUCTION

st.set_page_config(page_title=APP_TITLE, page_icon=PAGE_ICON, layout="centered")


def get_secret(name: str, default=None):
    """Look in Streamlit secrets first, then environment variables."""
    try:
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    return os.environ.get(name, default)


def require_password() -> None:
    """Simple shared-password gate. If no APP_PASSWORD is configured, access is open."""
    expected = get_secret("APP_PASSWORD")
    if not expected:
        return
    if st.session_state.get("auth_ok"):
        return
    st.title(f"{PAGE_ICON} {APP_TITLE}")
    st.caption("This screener is password-protected.")
    pw = st.text_input("Access password", type="password")
    if pw:
        if pw == expected:
            st.session_state.auth_ok = True
            st.rerun()
        st.error("Incorrect password — please try again.")
    st.stop()


require_password()

api_key = get_secret("GOOGLE_API_KEY")
if not api_key:
    st.error(
        "No GOOGLE_API_KEY is configured. Add it under the app's "
        "Settings → Secrets (or set it as an environment variable for local testing)."
    )
    st.stop()


@st.cache_resource(show_spinner=False)
def get_client(key: str):
    # vertexai=False forces the AI Studio (Gemini Developer API) endpoint and the
    # api_key, so an ambient GOOGLE_GENAI_USE_VERTEXAI / GOOGLE_CLOUD_PROJECT in the
    # host environment can't silently reroute us to Vertex AI (which rejects this key).
    return genai.Client(api_key=key, vertexai=False)


client = get_client(api_key)

# ---- Header + sidebar ----
st.title(f"{PAGE_ICON} {APP_TITLE}")
st.caption(APP_SUBTITLE)

with st.sidebar:
    st.markdown(f"### {PAGE_ICON} {APP_TITLE}")
    st.markdown(INTRO)
    st.divider()
    if st.button("🧹 New screening (clear chat)", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

if "messages" not in st.session_state:
    st.session_state.messages = []

# ---- Empty state ----
if not st.session_state.messages:
    st.info("Paste an article in the box below to get a screening decision.")
    with st.expander("See an example you can paste"):
        st.code(EXAMPLE, language="text")

# ---- History ----
for m in st.session_state.messages:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

# ---- New message ----
user_text = st.chat_input(INPUT_PLACEHOLDER)
if user_text:
    st.session_state.messages.append({"role": "user", "content": user_text})
    with st.chat_message("user"):
        st.markdown(user_text)

    contents = [
        {
            "role": "user" if m["role"] == "user" else "model",
            "parts": [{"text": m["content"]}],
        }
        for m in st.session_state.messages
    ]

    with st.chat_message("assistant"):
        placeholder = st.empty()
        answer = ""
        try:
            for chunk in client.models.generate_content_stream(
                model=MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=SCREENING_INSTRUCTION
                ),
            ):
                if chunk.text:
                    answer += chunk.text
                    placeholder.markdown(answer)
        except Exception as e:  # noqa: BLE001 — show a friendly message, keep the app alive
            answer = (
                "⚠️ Sorry — something went wrong talking to the model. "
                "Please try again in a moment.\n\n"
                f"_Technical detail: {e}_"
            )
            placeholder.markdown(answer)

    st.session_state.messages.append({"role": "assistant", "content": answer})
