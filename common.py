"""Shared helpers for both pages of the app: secrets, auth, and the Gemini client."""

import os

import streamlit as st
from google import genai


def get_secret(name: str, default=None):
    """Look in Streamlit secrets first, then environment variables."""
    try:
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:  # noqa: BLE001 — no secrets.toml locally is normal
        pass
    return os.environ.get(name, default)


def require_password(title: str, icon: str) -> None:
    """Shared-password gate. If no APP_PASSWORD is configured, access is open."""
    expected = get_secret("APP_PASSWORD")
    if not expected:
        return
    if st.session_state.get("auth_ok"):
        return
    st.title(f"{icon} {title}")
    st.caption("This tool is password-protected.")
    pw = st.text_input("Access password", type="password")
    if pw:
        if pw == expected:
            st.session_state.auth_ok = True
            st.rerun()
        st.error("Incorrect password — please try again.")
    st.stop()


def require_api_key() -> str:
    key = get_secret("GOOGLE_API_KEY")
    if not key:
        st.error(
            "No GOOGLE_API_KEY is configured. Add it under the app's "
            "Settings → Secrets (or set it as an environment variable for local testing)."
        )
        st.stop()
    return key


@st.cache_resource(show_spinner=False)
def get_client(key: str):
    # vertexai=False forces the AI Studio (Gemini Developer API) endpoint and the
    # api_key, so an ambient GOOGLE_GENAI_USE_VERTEXAI / GOOGLE_CLOUD_PROJECT in the
    # host environment can't silently reroute us to Vertex AI (which rejects this key).
    return genai.Client(api_key=key, vertexai=False)
