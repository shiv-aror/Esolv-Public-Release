# Deploy Esolv

Esolv has two parts: a FastAPI server and a Chrome extension. The server needs an HTTPS hostname. The extension is built locally and either loaded unpacked for testing or distributed through the Chrome Web Store or a managed Chrome deployment.

## 1. Host the API

Use a Linux server with Docker Compose v2 and a DNS name such as `api.example.org` pointing to it. Allow inbound ports 80 and 443. Caddy obtains and renews HTTPS certificates for that name.

Copy the repository to the server. In `backend`, copy `.env.example` to `.env` and set:

```dotenv
ESOLV_DOMAIN=api.example.org
ENV=prod
DEV_LOGIN=false
CANVAS_MOCK=false
OPENROUTER_API_KEY=your-new-key
GOOGLE_CLIENT_ID=your-google-oauth-web-client-id
ALLOWED_DOMAINS=mcpsmd.org
ALLOWED_EMAILS=arorashivum@gmail.com,srikarvinnamuri@gmail.com
JWT_SECRET=a-long-random-value
ENCRYPTION_KEY=a-fernet-key
CANVAS_REDIRECT_URI=https://api.example.org/canvas/oauth/callback
```

Generate `JWT_SECRET` with `python3 -c 'import secrets; print(secrets.token_urlsafe(48))'`. Generate `ENCRYPTION_KEY` with `python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'` in an environment that has `cryptography` installed. Keep `.env` private. Set Canvas OAuth client settings only if you have a district-approved Canvas Developer Key. The `data/docs` directory must contain the synced source snapshots and `manifest.json`; the container rebuilds the vector index at startup.

Run from `backend`:

```bash
docker compose -f docker-compose.yml -f compose.prod.yml up -d --build
curl https://api.example.org/health
```

The health response should be `{"ok":true}`. `docker compose -f docker-compose.yml -f compose.prod.yml logs -f esolv-api caddy` shows startup and HTTPS errors. The API's port 8000 is bound to loopback; Caddy handles public HTTPS.

To update the server after pulling new code, run the same `up -d --build` command. Back up the `esolv-state` Docker volume; it contains the SQLite database, encrypted Canvas tokens, and audit records. Use a database service and a proper secret store before scaling to multiple replicas.

## 2. Build and connect the extension

On your development computer:

```bash
cd frontend
npm ci
npm run build
```

For testing, open `chrome://extensions`, enable Developer mode, select **Load unpacked**, and choose `frontend/dist`. Pin Esolv, open its Settings, and set **Server** to `https://api.example.org`. Chrome will request permission to reach that hostname.

The extension ID shown in `chrome://extensions` determines its Google sign-in redirect: `https://<extension-id>.chromiumapp.org/`. Add that exact URI to the Google OAuth **Web application** client configured as `GOOGLE_CLIENT_ID`. A store-published build may have a different ID; add its redirect as well. The Google Workspace administrator may need to approve the OAuth client.

For broader distribution, zip the **contents** of `frontend/dist`, upload the zip in the Chrome Web Store Developer Dashboard, complete its listing/privacy fields, and submit it for review. Managed Chrome deployment is another district-controlled distribution path. After updating the extension, rebuild it and reload the unpacked version or submit a new store version.

## Before real student use

Use only district-approved Canvas and accommodations connections. The synthetic student CSV is for demonstrations. Rotate the Canvas and OpenRouter credentials previously shared in chat, and do not put credentials in the extension build or the repository. Have MCPS review the privacy policy, access model, and any production data handling before enabling real student records.
