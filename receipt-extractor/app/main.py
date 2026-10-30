"""
main.py
-------
The FastAPI web app. Run it with:   uv run uvicorn app.main:app --reload

The website (home, /app/, /contact/, ...) lives in the public/ folder.
On Vercel the CDN serves public/ directly; locally the mount at the bottom
of this file serves the same files, so the URLs are identical in both places.

Routes:
  GET  /health        -> quick "is the server alive" check
  GET  /settings      -> upload limits, so the web page uses the same rules as the server

  POST /extract       -> upload receipts, get JSON rows back
  POST /extract/csv   -> upload receipts, get a CSV file back            (for API users)
  POST /extract/xlsx  -> upload receipts, get the Excel report back      (for API users)

  POST /export/csv    -> send rows you ALREADY extracted, get a CSV       (no LLM call)
  POST /export/xlsx   -> send rows you ALREADY extracted, get the Excel   (no LLM call)
"""

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from app.config import (
    ALLOWED_EXTENSIONS,
    CATEGORIES,
    GROQ_API_KEY,
    MAX_FILE_SIZE_MB,
    MAX_FILES_PER_REQUEST,
    PROJECT_DIR,
)
from app.csv_export import rows_to_csv
from app.pipeline import process_file
from app.schemas import ReceiptRow
from app.xlsx_export import rows_to_xlsx

app = FastAPI(title="Receipt Extractor")

XLSX_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
MAX_EXPORT_ROWS = 1000


class ExportRequest(BaseModel):
    """Rows that the web page already has. Pydantic re-validates every field."""

    rows: list[ReceiptRow] = Field(max_length=MAX_EXPORT_ROWS)


# ---------- Helpers ----------
def _process_uploads(files: list[UploadFile]) -> list[ReceiptRow]:
    if not GROQ_API_KEY:
        raise HTTPException(status_code=500, detail="GROQ_API_KEY is missing. Add it to .env (local) or to the Vercel environment variables.")
    if not files:
        raise HTTPException(status_code=400, detail="Please upload at least one receipt.")
    if len(files) > MAX_FILES_PER_REQUEST:
        raise HTTPException(status_code=400, detail=f"Upload at most {MAX_FILES_PER_REQUEST} files at a time.")

    rows = []
    for upload in files:
        # Read one byte past the limit so we can reject big files without loading them fully
        data = upload.file.read(MAX_FILE_SIZE_MB * 1024 * 1024 + 1)
        rows.append(process_file(upload.filename or "", data))
    return rows


def _csv_response(rows: list[ReceiptRow]) -> Response:
    return Response(
        content=rows_to_csv(rows),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="expenses.csv"'},
    )


def _xlsx_response(rows: list[ReceiptRow]) -> Response:
    return Response(
        content=rows_to_xlsx(rows),
        media_type=XLSX_TYPE,
        headers={"Content-Disposition": 'attachment; filename="expense-report.xlsx"'},
    )


# ---------- Info ----------
@app.get("/health")
def health():
    return {"status": "ok", "api_key_set": bool(GROQ_API_KEY)}


@app.get("/settings")
def settings():
    return {
        "max_file_size_mb": MAX_FILE_SIZE_MB,
        "max_files": MAX_FILES_PER_REQUEST,
        "allowed_extensions": sorted(ALLOWED_EXTENSIONS),
        "categories": CATEGORIES,
    }


# ---------- Extract (calls the LLM) ----------
@app.post("/extract")
def extract(files: list[UploadFile] = File(...)):
    rows = _process_uploads(files)
    return {
        "total": len(rows),
        "ok": sum(r.status == "ok" for r in rows),
        "needs_review": sum(r.status == "needs_review" for r in rows),
        "errors": sum(r.status == "error" for r in rows),
        "rows": rows,
    }


@app.post("/extract/csv")
def extract_csv(files: list[UploadFile] = File(...)):
    return _csv_response(_process_uploads(files))


@app.post("/extract/xlsx")
def extract_xlsx(files: list[UploadFile] = File(...)):
    return _xlsx_response(_process_uploads(files))


# ---------- Export (no LLM call, just builds the file) ----------
@app.post("/export/csv")
def export_csv(request: ExportRequest):
    return _csv_response(request.rows)


@app.post("/export/xlsx")
def export_xlsx(request: ExportRequest):
    if not request.rows:
        raise HTTPException(status_code=400, detail="There are no rows to export.")
    return _xlsx_response(request.rows)


# ---------- Website (must stay LAST: it catches every path not matched above) ----------
# check_dir=False: on Vercel public/ is served by the CDN and may not be
# bundled with the Python function, so a missing folder must not crash startup.
app.mount("/", StaticFiles(directory=PROJECT_DIR / "public", html=True, check_dir=False), name="site")
