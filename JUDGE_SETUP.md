# Run Esolv locally

For the Congressional App Challenge judging period, any Google account will be allowed to access Esolv for demo purposes.

You need Chrome, Python 3.12, Node 20+, an OpenRouter API key, and a Google account.

1. Run `git clone https://github.com/shiv-aror/Esolv-Public-Release.git && cd Esolv-Public-Release`.
2. Run `cd frontend && npm ci && npm run build`.
3. In Chrome, open `chrome://extensions`, turn on Developer mode, click **Load unpacked**, and select the repo's `frontend/dist` folder.
4. Send the extension ID shown in Chrome and your Google email to the Esolv team. They will allow your account, add `https://<extension-id>.chromiumapp.org/` to the Google OAuth redirect URIs, and give you the client ID.
5. Back in the same terminal, run:

   ```bash
   cd ../backend
   python3.12 -m venv .venv
   .venv/bin/pip install -e .
   cp .env.example .env
   ```

6. In `backend/.env`, set `OPENROUTER_API_KEY`, `GOOGLE_CLIENT_ID`, `ALLOWED_EMAILS` (your email), and a random `JWT_SECRET`. Set `DEV_LOGIN=false` and leave `CANVAS_MOCK=true`. Keep this file private.
7. Run `.venv/bin/python -m app.rag.ingest`, then `.venv/bin/python -m uvicorn app.main:app --port 8000`.
8. Open Esolv from the Chrome toolbar, sign in with Google, and ask questions!
