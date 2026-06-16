# Self-Compassion Screener — web app

This `webapp/` folder is a complete, self-contained chat app. It wraps the **same**
screening prompt the ADK agent uses (`prompt.py` here is a copy of
`../screening_agent/prompt.py`) and calls Gemini directly, so it runs on the **free
Streamlit Community Cloud**. Your reviewer just opens a URL, types a password, and
chats — nothing to install on their side, ever.

**What the user sees:** a web page with a chat box. They paste a title + abstract and
get the INCLUDE / EXCLUDE / MAYBE decision with a confidence level, summary, checklist,
and notes.

---

## One-time deploy (~10 minutes)

You need a free **GitHub** account and a free **Streamlit** account
(sign in with GitHub at <https://share.streamlit.io>).

### 1. Put this folder in its own GitHub repo
The repo's root must be **this `webapp` folder**, so `streamlit_app.py` sits at the top
of the repo. From inside this folder:

```bash
git init
git add .
git commit -m "Self-compassion screening web app"
# Create an EMPTY repo on github.com first (no README), then:
git remote add origin https://github.com/<you>/<repo-name>.git
git branch -M main
git push -u origin main
```

`secrets.toml` is gitignored, so your API key is **never** pushed.

### 2. Deploy on Streamlit Community Cloud
1. Go to <https://share.streamlit.io> and sign in with GitHub.
2. **Create app → Deploy a public app from GitHub.**
3. Repository: your repo. Branch: `main`. Main file path: `streamlit_app.py`.
4. Open **Advanced settings**, set Python to 3.11+, and paste your **Secrets** in TOML:
   ```toml
   GOOGLE_API_KEY = "AQ.your-google-ai-studio-key"
   APP_PASSWORD   = "the-password-you-give-your-reviewer"
   ```
5. Click **Deploy**. In a minute or two you get a URL like
   `https://your-app-name.streamlit.app`.

### 3. Share
Send the reviewer the URL and the password. Done.

> Repeat these steps with the **urinary incontinence** app (in the other project's
> `webapp/` folder) as a **second repo** to get its own separate URL.

---

## Run it locally first (optional)
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # then edit the two values
streamlit run streamlit_app.py
```

## Updating later
- **Screening rules:** edit `prompt.py`, then `git push` — the app auto-redeploys.
  (If you also run the ADK agent, keep it in sync with `../screening_agent/prompt.py`.)
- **Wording / title / example article:** edit `config.py`, push.
- **API key or password:** change them in the app's **Settings → Secrets** — no code
  change or redeploy needed.

## Notes on the shared API key
- Both screeners can share one key; the page is password-gated so only your reviewer
  gets in.
- To track or limit/revoke usage per person, give each app its **own** free AI Studio
  key (<https://aistudio.google.com/apikey>) in its Secrets.
- On the free tier the app sleeps after inactivity and wakes in a few seconds on the
  next visit — harmless here.
