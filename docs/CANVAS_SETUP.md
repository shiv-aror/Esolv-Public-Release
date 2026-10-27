# Connecting Esolv to Canvas

Esolv talks to Canvas **read-only**, on behalf of the signed-in teacher, through the Canvas REST API. It never writes anything, and every student lookup is limited to courses that teacher teaches. The supplied PAT passed a read-only `/users/self` check on October 22, 2026, but has not been stored in a teacher account. Connect it through Settings after sign-in.

MCPS Canvas ("myMCPS Classroom") is at **https://mcpsmd.instructure.com**. That is already the default `CANVAS_BASE_URL`. MCPS student logins look like `studentID@mcpsmd.net`, and Esolv uses that as a fallback when Canvas's SIS ID field is empty or hidden.

## Option A: personal access token (works today, no admin needed, if MCPS allows it)
Each teacher: Canvas → **Account → Settings → "+ New Access Token"**, copy it, then Esolv → avatar menu → **Settings & Canvas → paste → Save**. Esolv checks it with `GET /api/v1/users/self`, stores it encrypted, and shows "Connected".
- **Unknown:** some districts turn off teacher-created tokens. If the "+ New Access Token" button isn't there, MCPS has disabled it and you need Option B.
- Tokens don't expire unless the teacher sets an expiry, so treat them like a password.

## Option B: OAuth ("Sign in with Canvas"), the proper production route
Needs an MCPS Canvas **account admin** to create a **Developer Key** (Admin → Developer Keys → + API Key):
1. **Redirect URI:** `https://<your-backend>/canvas/oauth/callback` (for local testing `http://localhost:8000/canvas/oauth/callback`). It must match `CANVAS_REDIRECT_URI` exactly.
2. Turn the key **ON**, and copy the **Client ID** and **Secret** into `backend/.env`: `CANVAS_CLIENT_ID`, `CANVAS_CLIENT_SECRET`.
3. If the key has **"Enforce Scopes"** on, set `CANVAS_OAUTH_SCOPES` to the read-only scopes (courses, course users, assignments, pages, custom gradebook columns, `users/self`). If it is off, leave it empty.
4. Canvas access tokens last one hour; Esolv refreshes them automatically with the stored refresh token.

## Checklist
| # | What | Who |
|---|------|-----|
| 1 | Confirm `CANVAS_BASE_URL=https://mcpsmd.instructure.com` | you |
| 2 | Try Option A with one real teacher account. If it works you can pilot immediately | a teacher |
| 3 | If tokens are disabled, ask MCPS Canvas admins for a Developer Key (Option B) | MCPS instructional technology |
| 4 | **Confirm where the student ID lives.** `CANVAS_STUDENT_ID_FIELD=auto` tries `sis_user_id`, then the part of `login_id` before `@`, then `integration_id`. Check one real roster | you |
| 5 | **Decide where accommodations come from.** Canvas has no built-in accommodations field. Today: a CSV (`ACCOMMODATIONS_PROVIDER=csv`) or a Canvas custom gradebook column named by `CANVAS_ACCOMMODATIONS_COLUMN`. The CSV provider never pulls from Synergy; with mock mode off it reads only `backend/data/accommodations.csv`, if supplied. If the data is in Synergy/another system, an approved manual export or new provider is needed | MCPS + you |
| 6 | Turn off the demo data: `CANVAS_MOCK=false`, otherwise users with no connected account see fake students | you |
| 7 | Host the backend on **HTTPS** (needed for OAuth redirect and so tokens never cross the network in the clear) | you |
| 8 | **Get MCPS approval.** Esolv reads student records and sends pseudonymized text to an AI provider. Expect MCPS to want a privacy/data-sharing review (FERPA, Maryland Student Data Privacy Act), a vendor review of OpenRouter and the model provider, and sign-off on the Privacy Policy/ToS drafts | MCPS privacy/IT |

## Test it without MCPS
Instructure gives teachers a free sandbox at **canvas.instructure.com** ("Free for Teacher"). Create a course, add a few test students, create a token there, then:
```
CANVAS_BASE_URL=https://canvas.instructure.com
CANVAS_MOCK=false
```
Restart the backend, reload the extension, paste the token in Settings, and ask "What courses do I teach?" or "Find student <name>".

## Where the code is
- `backend/app/canvas/client.py`: the read-only REST client (pagination, rate-limit backoff, 401 handling)
- `backend/app/canvas/oauth.py` and `tokens.py`: OAuth flow, refresh, encrypted storage
- `backend/app/mcp/canvas_server.py`: the tools the AI can call (`find_student`, `get_accommodations`, …), each scoped to the teacher's own courses
- `backend/app/providers/accommodations/`: where accommodation records come from
