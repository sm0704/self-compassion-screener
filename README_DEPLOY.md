# Self-Compassion Review Tools — web app

This `webapp/` folder is a complete, self-contained Streamlit app carrying **two tools**
behind one URL and one password:

- **Data extraction** (default page) — upload an included article's PDF and get every
  Covidence domain filled in, with a page reference, supporting quote, and confidence
  level behind each value. Nothing is submitted anywhere; the reviewer reads the result
  and types it into Covidence themselves.
- **Screening** — paste a Method section, get INCLUDE / EXCLUDE / MAYBE.

It calls Gemini directly via `google-genai`, so it needs no ADK and runs on the free
Streamlit Community Cloud. Your reviewer opens a URL, types a password, and works —
nothing to install on their side, ever.

---

## Layout

```
streamlit_app.py        entry point: page config, password gate, navigation
common.py               secrets, auth, cached Gemini client
config.py               all user-facing labels + which model each tool uses
views/
  extractor.py          the PDF extraction review page
  screener.py           the screening chat page
extraction/             COPY of ../extraction/ — schema, prompts, two-pass engine
prompt.py               COPY of ../screening_agent/prompt.py
```

The two `COPY` entries are generated. Edit the originals in the parent project and run
`../sync_webapp.sh`; editing them here will be overwritten.

## One-time deploy (~10 minutes)

You need a free **GitHub** account and a free **Streamlit** account
(sign in with GitHub at <https://share.streamlit.io>).

### 1. Put this folder in its own GitHub repo
The repo's root must be **this `webapp` folder**, so `streamlit_app.py` sits at the top
of the repo. From inside this folder:

```bash
git init
git add .
git commit -m "Self-compassion review tools"
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

---

## Run it locally first (optional)
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .streamlit/secrets.toml.example .streamlit/secrets.toml   # then edit the two values
streamlit run streamlit_app.py
```

## Updating later
- **Extraction rules or output shape:** edit `../extraction/prompt.py` or
  `../extraction/schema.py`, run `../sync_webapp.sh`, then `git push` from here.
- **Screening rules:** edit `../screening_agent/prompt.py`, run `../sync_webapp.sh`, push.
- **Wording, titles, models, example article:** edit `config.py`, push.
- **API key or password:** change them in the app's **Settings → Secrets** — no code
  change or redeploy needed.

## Notes

- **Models.** Extraction defaults to `gemini-3.1-pro-preview` (set in `config.py`);
  dense tables and statistical judgement are where a cheaper tier stops being worth it.
  The sidebar has a selector so you can compare tiers on the same article. Screening
  stays on Flash.
- **Which page opens first.** Data extraction is the default because that is the stage
  in progress. Move `default=True` in `streamlit_app.py` to change it.
- **Upload size.** `.streamlit/config.toml` sets `maxUploadSize = 200` (MB). Ordinary
  articles are a few MB; theses with embedded figures can be much larger.
- **Runtime.** A full paper takes a minute or two — two passes over the whole PDF. The
  result is cached in the session, so switching domain tabs costs nothing.
- **Shared API key.** Both tools share one key; the app is password-gated. To track or
  revoke usage separately, give each deployment its own free AI Studio key
  (<https://aistudio.google.com/apikey>) in its Secrets.
- **Sleeping.** On the free tier the app sleeps after inactivity and wakes in a few
  seconds — harmless here.
