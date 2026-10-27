# Real-Chrome end-to-end test

Loads the built extension into Chrome for Testing (branded Chrome 137+ ignores `--load-extension`), opens a localhost page,
injects the panel and checks: sign-in, bottom-left resize, header drag, "This page" context, a cited + fact-checked answer,
tab screenshot → vision answer, close/reopen, and the regular-tab fallback on `chrome://` pages.

```bash
cd frontend
npm run build:e2e                                   # dist-test/ (adds <all_urls> so automation can inject/capture)
npx @puppeteer/browsers install chrome@stable --path .chrome-for-testing
(cd e2e && mkdir -p page && printf '<!doctype html><title>e2e</title><h1>MCPS ELD Resources</h1><p id=p>ELD paperwork is due on a timeline that varies with the date of enrollment.</p>' > page/index.html && python3 -m http.server 5175 --directory page &)
# backend must be running on :8000 with DEV_LOGIN=true and an OPENROUTER_API_KEY
CHROME_BIN="$(find .chrome-for-testing -name 'Google Chrome for Testing' -type f | head -1)" npm run e2e
```
