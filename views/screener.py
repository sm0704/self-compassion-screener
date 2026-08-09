"""Screening view — paste a Method section, get INCLUDE / EXCLUDE / MAYBE.

Unchanged in behaviour from the original single-page app; it now lives behind
st.navigation alongside the extraction tool.
"""

import streamlit as st
from google.genai import types

from common import get_client, require_api_key
from config import (
    APP_SUBTITLE,
    APP_TITLE,
    EXAMPLE,
    INPUT_PLACEHOLDER,
    INTRO,
    MODEL,
    PAGE_ICON,
)
from prompt import SCREENING_INSTRUCTION


def render() -> None:
    client = get_client(require_api_key())

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

    if not st.session_state.messages:
        st.info("Paste an article in the box below to get a screening decision.")
        with st.expander("See an example you can paste"):
            st.code(EXAMPLE, language="text")

    for m in st.session_state.messages:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])

    user_text = st.chat_input(INPUT_PLACEHOLDER)
    if not user_text:
        return

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
