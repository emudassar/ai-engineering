"""
make_samples.py
---------------
Creates a few fake receipts (PDF + PNG) and their answer key (labels.json),
so you can try the evaluation right away.

For your REAL accuracy number: put 30 real receipts in evaluation/receipts/
and write their correct values in labels.json by hand (same format).

Needs the dev tools:  uv sync   (reportlab + pillow are in the dev group)
Run:                  uv run python evaluation/make_samples.py
"""

import json
from pathlib import Path

from PIL import Image, ImageDraw
from reportlab.lib.pagesizes import A6
from reportlab.pdfgen import canvas

OUT_DIR = Path(__file__).parent / "receipts"
LABELS_FILE = Path(__file__).parent / "labels.json"

# Each sample = the lines printed on the receipt + the CORRECT answer.
# A None in the answer means "this info is not on the receipt".
SAMPLES = {
    "coffee.pdf": {
        "lines": ["BLUE BOTTLE COFFEE", "Date: 2026-03-04", "Latte  5.50", "Muffin  3.75", "Subtotal  9.25", "Tax  0.74", "TOTAL  $9.99"],
        "answer": {"date": "2026-03-04", "vendor": "Blue Bottle Coffee", "amount": 9.99, "tax": 0.74, "currency": "USD", "category": "Meals"},
    },
    "taxi.pdf": {
        "lines": ["CITY CAB CO.", "Trip date: 12 January 2026", "Airport -> Hotel", "Fare  42.00", "VAT (10%)  4.20", "Total paid  EUR 46.20"],
        "answer": {"date": "2026-01-12", "vendor": "City Cab Co.", "amount": 46.20, "tax": 4.20, "currency": "EUR", "category": "Travel"},
    },
    "office.pdf": {
        "lines": ["STAPLES", "2026-02-18", "Printer paper x5  24.95", "Pens  6.40", "Sales tax  2.52", "Total  $33.87"],
        "answer": {"date": "2026-02-18", "vendor": "Staples", "amount": 33.87, "tax": 2.52, "currency": "USD", "category": "Office Supplies"},
    },
    "software.pdf": {
        "lines": ["GITHUB, INC.", "Invoice date: 2026-04-01", "Copilot Pro - monthly", "Total  $10.00", "Tax  $0.00"],
        "answer": {"date": "2026-04-01", "vendor": "GitHub", "amount": 10.00, "tax": 0.00, "currency": "USD", "category": "Software"},
    },
    "grocery_no_tax.pdf": {
        "lines": ["FRESH MART", "Date: 2026-05-09", "Milk  2.10", "Bread  1.80", "Eggs  3.40", "TOTAL  GBP 7.30"],
        "answer": {"date": "2026-05-09", "vendor": "Fresh Mart", "amount": 7.30, "tax": None, "currency": "GBP", "category": "Groceries"},
    },
    "no_date.pdf": {
        "lines": ["LAHORE BIRYANI HOUSE", "Chicken Biryani  Rs 850", "Cold Drink  Rs 120", "GST  Rs 156", "TOTAL  Rs 1126"],
        "answer": {"date": None, "vendor": "Lahore Biryani House", "amount": 1126.0, "tax": 156.0, "currency": "PKR", "category": "Meals"},
    },
    "photo_pharmacy.png": {
        "lines": ["GREEN CROSS PHARMACY", "Date: 2026-06-21", "Vitamin D  12.00", "Bandages  4.50", "Tax  1.32", "TOTAL  $17.82"],
        "answer": {"date": "2026-06-21", "vendor": "Green Cross Pharmacy", "amount": 17.82, "tax": 1.32, "currency": "USD", "category": "Health"},
    },
}


def make_pdf(path: Path, lines: list[str]) -> None:
    pdf = canvas.Canvas(str(path), pagesize=A6)
    y = A6[1] - 30
    for line in lines:
        pdf.drawString(20, y, line)
        y -= 18
    pdf.save()


def make_png(path: Path, lines: list[str]) -> None:
    image = Image.new("RGB", (420, 60 + 28 * len(lines)), "white")
    draw = ImageDraw.Draw(image)
    y = 20
    for line in lines:
        draw.text((20, y), line, fill="black")
        y += 28
    image.save(path)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    labels = {}
    for name, sample in SAMPLES.items():
        path = OUT_DIR / name
        if name.endswith(".pdf"):
            make_pdf(path, sample["lines"])
        else:
            make_png(path, sample["lines"])
        labels[name] = sample["answer"]

    LABELS_FILE.write_text(json.dumps(labels, indent=2), encoding="utf-8")
    print(f"Created {len(SAMPLES)} sample receipts in {OUT_DIR} and {LABELS_FILE.name}")


if __name__ == "__main__":
    main()
