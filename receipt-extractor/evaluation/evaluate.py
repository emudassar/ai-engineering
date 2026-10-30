"""
evaluate.py
-----------
Measures how accurate the extractor is.

How it works:
  1. labels.json holds the CORRECT answer for every receipt (you write it by hand).
  2. We run the real extractor on each receipt in evaluation/receipts/.
  3. We compare field by field and print accuracy.

A field is correct when it matches the label. If the label is null (info not on
the receipt), the extractor must ALSO return null: that proves it did not guess.

Run:  uv run python evaluation/evaluate.py
"""

import json
import re
import sys
import time
from pathlib import Path

# Make "import app" work when running this file directly
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import FIELDS  # noqa: E402
from app.pipeline import process_file  # noqa: E402

RECEIPTS_DIR = Path(__file__).parent / "receipts"
LABELS_FILE = Path(__file__).parent / "labels.json"
PAUSE_SECONDS = 2  # small pause between files to stay under rate limits


def _clean_text(value) -> str:
    return re.sub(r"[^a-z0-9]", "", str(value).lower())


def is_correct(field: str, predicted, expected) -> bool:
    """Compare one predicted field against the label."""
    if expected is None or predicted is None:
        return expected is None and predicted is None
    if field in ("amount", "tax"):
        return abs(float(predicted) - float(expected)) < 0.01
    if field == "vendor":
        # "Staples Inc" and "Staples" count as the same vendor
        a, b = _clean_text(predicted), _clean_text(expected)
        return a == b or a in b or b in a
    return _clean_text(predicted) == _clean_text(expected)


def main() -> None:
    if not LABELS_FILE.exists():
        sys.exit("labels.json not found. Run:  uv run python evaluation/make_samples.py")

    labels = json.loads(LABELS_FILE.read_text(encoding="utf-8"))
    correct = {field: 0 for field in FIELDS}
    checked = 0
    failed_files = []

    for filename, expected in labels.items():
        path = RECEIPTS_DIR / filename
        if not path.exists():
            print(f"SKIP  {filename} (file not found)")
            continue

        row = process_file(filename, path.read_bytes())
        if row.status == "error":
            print(f"ERROR {filename}: {row.notes}")
            failed_files.append(filename)
            time.sleep(PAUSE_SECONDS)
            continue

        checked += 1
        wrong = []
        for field in FIELDS:
            if is_correct(field, getattr(row, field), expected.get(field)):
                correct[field] += 1
            else:
                wrong.append(f"{field}: got {getattr(row, field)!r}, expected {expected.get(field)!r}")
        print(f"{'OK   ' if not wrong else 'DIFF '} {filename}")
        for line in wrong:
            print(f"        {line}")
        time.sleep(PAUSE_SECONDS)

    # ---------- Report ----------
    if checked == 0:
        sys.exit("No receipt could be evaluated.")

    print(f"\nReceipts evaluated: {checked}  (failed to run: {len(failed_files)})")
    print("-" * 36)
    for field in FIELDS:
        print(f"{field:<10} {correct[field]}/{checked}  {correct[field] / checked:.0%}")
    total_right = sum(correct.values())
    total = checked * len(FIELDS)
    print("-" * 36)
    print(f"OVERALL FIELD ACCURACY: {total_right}/{total} = {total_right / total:.1%}")


if __name__ == "__main__":
    main()
