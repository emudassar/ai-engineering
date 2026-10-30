# Receipt → Expense Sheet Extractor

Upload receipt PDFs or photos, get a clean CSV with
**date, vendor, amount, tax, currency, category**.
If a field is missing, the row is **flagged** (`needs_review`), never guessed.

## Course concepts used

| Concept | Where |
|---|---|
| Pydantic schemas + validators | `app/schemas.py` |
| `json_object` output + schema in the prompt | `app/extractor.py` |
| Retry on bad JSON | `app/extractor.py` |
| pypdf (PDF text extraction) | `app/readers.py` |
| FastAPI + file upload | `app/main.py` |
| Evaluation (labelled data, accuracy) | `evaluation/` |

## How it works

```
upload  ->  readers.py   ->  extractor.py  ->  validation.py  ->  csv_export.py
(file)      PDF -> text      LLM -> JSON       flag missing        rows -> CSV
            image -> base64  -> Pydantic       fields
```

`pipeline.py` glues these steps together for one file and **never crashes**:
a bad file becomes a row with `status = error` and the other files still finish.

## Project layout

```
receipt-extractor/
├── app/
│   ├── config.py        settings: models, limits, categories
│   ├── schemas.py       Pydantic models + data cleaning
│   ├── readers.py       PDF/image reading + file checks
│   ├── extractor.py     the LLM call (only file that talks to Groq)
│   ├── validation.py    flags missing/odd values
│   ├── pipeline.py      one file -> one row
│   ├── csv_export.py    rows -> CSV
│   └── main.py          FastAPI routes (+ serves public/ locally)
├── public/              the website (Vercel serves this from its CDN)
│   ├── index.html       landing page
│   ├── app/             the upload tool
│   ├── contact/  privacy/  terms/  404.html
│   └── assets/          site.css (built by Tailwind), site.js (header/footer), app.js
├── tailwind/input.css   Tailwind source: theme colours, fonts, components
├── package.json         `npm run build:css` / `npm run watch:css`
├── main.py              Vercel entry point (imports app.main:app)
├── evaluation/          accuracy measurement
├── tests/               offline tests (LLM is faked)
└── pyproject.toml
```

## Styling (Tailwind)

The site uses Tailwind CSS v4. Pages use utility classes; `tailwind/input.css` holds the
theme and a few shared components. After changing classes, rebuild the CSS:

```powershell
npm install
npm run build:css      # or: npm run watch:css while editing
```

The built `public/assets/site.css` is committed, so deploying needs no Node build step.

## Setup

```powershell
cd receipt-extractor
uv sync
```

Your `GROQ_API_KEY` is read **only** from the `.env` file in this folder (see
`.env.example`), so the app behaves the same locally and on Vercel.

## Run

```powershell
uv run uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000 for the website, or http://127.0.0.1:8000/app/ for the tool.

Or use the API directly:

```powershell
curl -X POST http://127.0.0.1:8000/extract/csv -F "files=@receipt1.pdf" -F "files=@photo.jpg" -o expenses.csv
```

| Route | What it does |
|---|---|
| `GET /` | website (`/app/` is the upload tool) |
| `GET /health` | server + API-key check |
| `POST /extract` | JSON rows (+ the CSV text) |
| `POST /extract/csv` | CSV download |
| `POST /extract/xlsx` | formatted Excel download |

## CSV columns

`file, date, vendor, amount, tax, currency, category, status, notes`

Use the **Excel download** (`.xlsx`) for a ready-to-read sheet: sized columns (no `####`), real dates and numbers, coloured rows (yellow = needs review, red = error), frozen header and filters. The CSV is there for importing into other tools.

* `status`: `ok` · `needs_review` (a field is missing or odd, see `notes`) · `error` (file could not be processed)
* `tax` empty is allowed (many receipts have none), so it does not trigger review.

## Errors that are handled

Unsupported file type · empty file · file over 4 MB · corrupted or password-protected
PDF · scanned PDF without text · more than 20 files · missing/invalid API key ·
rate limit · no internet · model returns invalid JSON (retried once) · dates that
do not exist · `$1,234.50`-style numbers · categories outside the allowed list.

## Measure accuracy

```powershell
uv run python evaluation/make_samples.py   # 7 fake demo receipts + labels.json
uv run python evaluation/evaluate.py       # prints per-field accuracy
```

The demo samples are synthetic and easy. For a number you can quote:

1. Put 30 **real** receipts in `evaluation/receipts/`.
2. Add each one to `evaluation/labels.json` by hand (use `null` when the info is not on the receipt).
3. Run `evaluate.py` and quote the result, e.g. *"Extracts 6 fields from receipts at X% field accuracy across 30 labelled samples."*

Do not quote the demo score as your real accuracy.

## Deploy to Vercel

1. Push the repo to GitHub and import it in Vercel.
2. **Root Directory**: `receipt-extractor` (Vercel detects FastAPI from `main.py`).
3. **Environment Variables**: add `GROQ_API_KEY`. Optional: `TEXT_MODEL`, `VISION_MODEL`.
4. Deploy. `public/` is served by the CDN; every other path (`/extract`, `/health`, `/docs`, ...) goes to FastAPI.

Notes:
* Vercel rejects request bodies over 4.5 MB, so files are limited to **4 MB** each
  (`MAX_FILE_SIZE_MB`). The web page sends one file per request, so batches of 20 still work.
* Set your contact email in `public/assets/site.js` (`SITE.contactEmail`).

## Tests

```powershell
uv run pytest
```

## Limits worth knowing

* Receipt **photos** use a vision model (`qwen/qwen3.8-27b` by default). Blurry or
  rotated photos will produce more `needs_review` rows.
* Scanned PDFs have no text layer: upload them as PNG/JPG instead.
* Files are processed one after another, so 20 receipts can take a minute or two.
* Uploads are processed in memory and not stored.
