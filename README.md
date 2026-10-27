 Esolv
Prefer not to install anything? Watch our demo video. Everything below is optional.

Quick local demo (about 15 minutes): Chrome, Python 3.12, Node 20+, and an OpenRouter API key (email us for a limited demo key).

1. git clone https://github.com/shiv-aror/Esolv-Public-Release.git && cd Esolv-Public-Release
2. cd frontend && npm ci && npm run build
3. In Chrome, open chrome://extensions, turn on Developer mode, click Load unpacked, and select frontend/dist.
4. cd ../backend && python3.12 -m venv .venv && .venv/bin/pip install -e . && cp .env.example .env (on Windows, use .venv\Scripts\ instead of .venv/bin/)
5. In backend/.env, set OPENROUTER_API_KEY and any random JWT_SECRET. Leave DEV_LOGIN=true and CANVAS_MOCK=true.
6. .venv/bin/python -m app.rag.ingest, then .venv/bin/python -m uvicorn app.main:app --port 8000
7. Open Esolv from the Chrome toolbar and use the demo sign-in.

Try asking:

“How long do we monitor a student after they exit ELD?” (click a citation number)
“What accommodations does student 123456 have?” (synthetic demo student)
“What is Fairfax County’s ELD exit policy?” (Esolv says it can’t answer instead of guessing)

Optional: real Google sign-in. Send us your extension ID and email, and we’ll add you. 

