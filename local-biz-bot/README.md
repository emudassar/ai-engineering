# Local Biz Bot

A chatbot a local business adds to its website with one `<script>` tag.
It reads the business's own website and answers visitor questions about prices,
hours, services and service areas. When it doesn't know an answer, it gives the
phone number and offers a call-back form instead of guessing.

There are two interfaces:
- **Owner dashboard** (`/dashboard`): add a website, see what the bot learned, test it, copy the install code, and see leads.
- **Chat widget** (`widget.js`): the bubble visitors use on the business website.

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
| `app/main.py` | FastAPI: `/chat`, `/lead`, serves the widget and dashboard |
| `app/admin.py` | Dashboard API under `/admin`, protected by `ADMIN_KEY` |
| `app/onboard.py` | Add or refresh a website (used by the dashboard and as a CLI) |
| `app/leads.py` | CLI: show call-back requests |
| `dashboard/` | Owner dashboard: `index.html`, `style.css`, `app.js` (plain JS) |
| `widget/widget.js` | The chat bubble (plain JS, Shadow DOM) |
| `sample_site/` | A made-up plumbing business for testing |

## Run it

1. Put `GROQ_API_KEY` and `ADMIN_KEY` in a `.env` file (see `.env.example`). Without `QDRANT_URL`, data is stored in a local `qdrant_data/` folder.
2. Serve the sample business site:
   ```bash
   uv run python -m http.server 8001 --directory sample_site
   ```
3. In a second terminal, start the API:
   ```bash
   uv run uvicorn app.main:app --port 8000
   ```
4. Open http://localhost:8000, sign in with your `ADMIN_KEY`, click **+ Add website** and enter `http://localhost:8001`.
5. Open http://localhost:8001 and click the chat bubble.

The same steps also work from the command line (with local Qdrant, stop the API first, since only one process can open the local folder):
```bash
uv run python -m app.onboard http://localhost:8001
```
```bash
uv run python -m app.leads localhost-8001
```

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

## Test results (sample site)

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
