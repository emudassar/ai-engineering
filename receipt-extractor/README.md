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
│   ├── main.py          FastAPI routes
│   └── static/index.html  upload page
├── evaluation/          accuracy measurement
├── tests/               offline tests (LLM is faked)
└── pyproject.toml
```

## Setup

```powershell
cd receipt-extractor
uv sync
```

Your `GROQ_API_KEY` is read from a `.env` file in this folder **or any parent
folder** (so the course-root `.env` already works). See `.env.example`.

## Run

```powershell
uv run uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000, choose receipts, click **Extract**, then **Download CSV**.

Or use the API directly:

```powershell
curl -X POST http://127.0.0.1:8000/extract/csv -F "files=@receipt1.pdf" -F "files=@photo.jpg" -o expenses.csv
```

| Route | What it does |
|---|---|
| `GET /` | upload page |
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

Unsupported file type · empty file · file over 10 MB · corrupted or password-protected
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
