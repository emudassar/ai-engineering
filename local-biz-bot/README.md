# Local Biz Bot

A chatbot a local business adds to its website with one `<script>` tag.
It reads the business's own website and answers visitor questions about prices,
hours, services and service areas. When it doesn't know an answer, it gives the
phone number and offers a call-back form instead of guessing.

There are three interfaces:
- **Product website** (`/`): the Local Biz Bot landing site (home, features, how it works, use cases, about,
  contact, privacy). It runs its own chatbot, so the site itself is the live demo, and its contact form saves leads.
- **Owner dashboard** (`/dashboard/`): add a website, see what the bot learned, test it, copy the install code, and see leads.
- **Chat widget** (`/static/widget.js`): the bubble visitors use on the business website.

## How it works

```
ONBOARDING (dashboard or CLI, once per website)                  CHAT (every visitor question)
─────────────────────────────                  ─────────────────────────────
website URL                                    widget.js on the business site
   │  crawl.py: sitemap → pages → clean text      │  POST /chat {site_id, message}
   ├─► make_chunks ──► Qdrant (type="chunk")      ▼
   │                                           main.py: check the Origin header
   └─► profile.py: LLM → BusinessProfile          │
          └──────────► Qdrant (type="profile")    ▼
                                               chat.py builds the prompt from:
                                                 1. business profile (exact facts)
                                                 2. "open now?" computed in hours.py
                                                 3. top 4 chunks from Qdrant (RAG)
                                                  │
                                                  ▼
                                               LLM → {"answer", "handoff"}
                                               handoff=true → call-back form → POST /lead
```

## Project structure

| File | Job |
|---|---|
| `app/config.py` | Settings and shared clients (Groq, Qdrant, embedding model) |
| `app/crawl.py` | Find pages via sitemap, download, clean HTML, split into chunks |
| `app/profile.py` | `BusinessProfile` Pydantic model + LLM extraction |
| `app/hours.py` | "Are you open now?" calculated in code with time zones |
| `app/store.py` | Every Qdrant read and write |
| `app/chat.py` | Builds the prompt and answers one question |
| `app/main.py` | FastAPI: `/chat`, `/lead`, and serves `public/` locally |
| `app/admin.py` | Dashboard API under `/admin`, protected by `ADMIN_KEY` |
| `app/onboard.py` | Add or refresh a website (used by the dashboard and as a CLI) |
| `app/leads.py` | CLI: show call-back requests |
| `api/index.py` | Vercel entry point (imports the FastAPI app) |
| `public/*.html`, `public/assets/` | The product website (plain HTML/CSS/JS) |
| `public/dashboard/` | Owner dashboard: `index.html`, `style.css`, `app.js` (plain JS) |
| `public/static/widget.js` | The chat bubble (plain JS, Shadow DOM) |
| `vercel.json` | Sends `/chat`, `/lead`, `/admin/*` to the Python function; everything else is static |

## Run it locally

1. Copy `.env.example` to `.env` and fill in `GROQ_API_KEY` and `ADMIN_KEY`. Without `QDRANT_URL`, data is stored
   in a local `qdrant_data/` folder. Only this folder's `.env` is read.
2. Start the app:
   ```bash
   uv run uvicorn app.main:app --port 8000
   ```
3. Open http://localhost:8000/dashboard/, sign in with your `ADMIN_KEY`, click **+ Add website** and enter
   `http://localhost:8000`. The bot reads the product website.
4. Open http://localhost:8000 and click the chat bubble, or any "Try the live demo" button.

The widget on the product site works out its `site_id` from the current domain (`public/assets/site.js`), so the
same HTML works on localhost and on the live domain, as long as that domain has been added in the dashboard.

Parts of a page that the bot should NOT learn from (for example the example conversations and the dashboard mockup
on the homepage) are marked with a `data-nobot` attribute, and the crawler skips them.

CLI equivalents (with local Qdrant, stop the API first, since only one process can open the local folder):
```bash
uv run python -m app.onboard http://localhost:8000
```
```bash
uv run python -m app.leads localhost-8000
```

## Deploy to Render (free, recommended)

A Render web service runs the whole app (website + API) as one normal Python server.

Live demo: https://local-biz-bot-qxl6.onrender.com (deployed from the standalone
[emudassar/local-biz-bot](https://github.com/emudassar/local-biz-bot) repo).

1. In Render create a free **Web Service** from this repo (or **New → Blueprint**, which reads `render.yaml`).
   Build command `pip install -r requirements.txt`, start command
   `uvicorn app.main:app --host 0.0.0.0 --port $PORT`, environment variable `PYTHON_VERSION=3.12.8`.
2. Render asks for the secrets: `GROQ_API_KEY`, `ADMIN_KEY`, `QDRANT_URL`, `QDRANT_API_KEY`. Use Qdrant Cloud:
   the free service's disk is wiped on every deploy and restart.
3. On startup the app adds its own `*.onrender.com` address as a site (`onboard_self()` in `app/onboard.py`), so the
   live demo works without the dashboard. Every push to `main` redeploys.

The free service sleeps after 15 minutes without visitors; the next visit wakes it in about a minute.

## Deploy to Vercel

1. Push this folder to GitHub (or run `vercel` from inside it). In Vercel, import the repo and set
   **Root Directory** to `local-biz-bot`. Framework preset: **Other**.
2. In **Settings → Environment Variables** add `GROQ_API_KEY`, `ADMIN_KEY`, `QDRANT_URL`, `QDRANT_API_KEY`
   (Qdrant Cloud is required: serverless functions can't keep a local database folder), and
   `BACKEND_URL` = your deployment URL, e.g. `https://local-biz-bot.vercel.app`.
3. Deploy. Then open `https://<your-domain>/dashboard/`, sign in, and **+ Add website** with
   `https://<your-domain>`, so the site's own chatbot and contact form start working.
4. If you later add a custom domain, add that domain in the dashboard too (each domain gets its own `site_id`).

Notes:
- Dependencies come from `requirements.txt` (made with `uv export --no-hashes --no-dev --no-emit-project -o requirements.txt`;
  run it again after changing dependencies).
- The embedding model (~90 MB) is downloaded on each cold start, so the first chat after a quiet period is slower.
- Adding a website crawls for 20-60 s; `vercel.json` allows the function 60 s.
- If the build complains about the Python version, change `.python-version` to `3.12`.

## Design decisions (interview notes)

- **Profile + RAG, not RAG alone.** Phone, hours and prices are the most-asked questions. They're extracted once into a fixed structure and sent with every question, so the answer never depends on whether vector search happened to find the right chunk.
- **"Open now?" is computed in code.** LLMs are unreliable with dates and time zones. `hours.py` works out the answer and hands the LLM a ready-made sentence.
- **No invented prices.** The prompt allows only prices that appear in the context; otherwise the bot hands off to the owner.
- **Handoff and lead capture.** An unanswered question becomes a call-back request, which gives the business owner real value.
- **One database.** Chunks, profiles and leads all live in one Qdrant collection, separated by `type` and `site_id` payload fields. One collection serves many businesses.
- **Origin check.** Each `site_id` only works from its own domain, so a copied snippet can't spend our LLM budget elsewhere.
- **Admin key.** Dashboard routes can crawl websites (LLM cost) and show visitors' phone numbers, so every `/admin` route checks the `X-Admin-Key` header with `secrets.compare_digest`.
- **No framework for the UI.** The dashboard and widget are plain HTML/CSS/JS served by FastAPI. There's no build step, and the whole app runs with one command.
- **Prompt injection.** Website text is treated as data. Visitors can only send `user`/`assistant` messages, never `system`.
- **Safe widget.** Shadow DOM isolates the CSS, and replies are inserted with `textContent`, so they can't inject HTML.

## Test results (plumbing test site, earlier version)

| Question | Result |
|---|---|
| How much is drain cleaning? | "$129 flat rate" ✅ |
| Are you open right now? (5:37 AM Friday, Austin) | Closed, opens 8:00 ✅ |
| Do you serve Round Rock? | Yes ✅ |
| Can you pump my septic tank? | No (the site says so) ✅ |
| How much to replace a kitchen sink? | Doesn't know → phone number + call-back form ✅ |
| Off-topic and "ignore your rules" questions | Refused, handed off ✅ |
| Request from another domain | 403 blocked ✅ |

## Not included yet (next steps)

- Rate limiting per IP (e.g. slowapi)
- Emailing new leads to the owner
- Scheduled weekly re-crawl (for now, run `onboard` again)
- An evaluation set across several real websites to measure accuracy
