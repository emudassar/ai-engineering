"""
xlsx_export.py
--------------
Builds a formatted Excel report from the result rows.

Everything is on ONE sheet, from top to bottom:
  1. Title banner
  2. KPI cards (receipts / ready / needs review / errors)
  3. "Spending by category" table  +  pie chart next to it
  4. "All receipts" table (one colour-coded row per receipt)

Why Excel and not only CSV? A CSV can not store colours or column widths
(that is why Excel shows "#####" for dates in a CSV).
"""

import io
from datetime import date

from openpyxl import Workbook
from openpyxl.chart import PieChart, Reference
from openpyxl.chart.label import DataLabelList
from openpyxl.chart.series import DataPoint
from openpyxl.formatting.rule import DataBarRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

from app.csv_export import safe_cell
from app.schemas import ReceiptRow

# ---------- Colour palette ----------
NAVY = "1F3864"
BLUE = "2F5597"
LIGHT_GREY = "F2F4F8"
MID_GREY = "D9DEE7"
TEXT_GREY = "595959"
WHITE = "FFFFFF"

# Each category gets its own (background, text) colour so the sheet is easy to scan.
CATEGORY_COLORS = {
    "Meals": ("FCE4D6", "843C0C"),
    "Travel": ("DDEBF7", "1F4E79"),
    "Office Supplies": ("E2EFDA", "375623"),
    "Software": ("E8E0F5", "4B2C8C"),
    "Utilities": ("FFF2CC", "7F6000"),
    "Groceries": ("D5F0E3", "0B6E4F"),
    "Entertainment": ("FADBD8", "922B21"),
    "Health": ("D0EEF5", "0E6E80"),
    "Other": ("EDEDED", "404040"),
}
UNCATEGORIZED = ("F8F8F8", "7F7F7F")

# Status -> (badge text, badge background, badge text colour, light row tint)
STATUS_STYLES = {
    "ok": ("✔ Ready", "C6EFCE", "006100", None),
    "needs_review": ("⚠ Review", "FFEB9C", "9C5700", "FFF9E6"),
    "error": ("✖ Error", "FFC7CE", "9C0006", "FDEEEF"),
}

THIN = Side(style="thin", color=MID_GREY)
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
CENTER = Alignment(horizontal="center", vertical="center")
LEFT = Alignment(horizontal="left", vertical="center", indent=1)
RIGHT = Alignment(horizontal="right", vertical="center", indent=1)

# ---------- Sheet grid ----------
# Column A is a small left margin. Columns B..J hold the receipts table;
# the summary parts above reuse the same columns.
# (column letter, title, ReceiptRow attribute, width)
RECEIPT_COLUMNS = [
    ("B", "File", "file", 22),
    ("C", "Date", "date", 14),
    ("D", "Vendor", "vendor", 30),
    ("E", "Category", "category", 18),
    ("F", "Amount", "amount", 14),
    ("G", "Tax", "tax", 12),
    ("H", "Currency", "currency", 11),
    ("I", "Status", "status", 14),
    ("J", "Notes", "notes", 42),
]
FIRST_COL, LAST_COL = "B", "J"

# KPI cards: (first column, last column) of each card, chosen so all 4 are about the same width
CARD_SPANS = [("B", "C"), ("D", "D"), ("E", "F"), ("G", "I"), ("J", "J")]

CHART_HEIGHT_ROWS = 15  # how many rows the pie chart covers (used to place the next section)


def _fill(color: str) -> PatternFill:
    return PatternFill("solid", fgColor=color)


def _category_colors(category: str | None) -> tuple[str, str]:
    return CATEGORY_COLORS.get(category or "", UNCATEGORIZED)


def _section_title(sheet, cell_range: str, text: str) -> None:
    """Navy heading with an underline, e.g. "Spending by category"."""
    sheet.merge_cells(cell_range)
    cell = sheet[cell_range.split(":")[0]]
    cell.value = text
    cell.font = Font(size=14, bold=True, color=NAVY)
    # A merged cell only shows the borders of each cell inside it, so underline them all
    for row in sheet[cell_range]:
        for part in row:
            part.border = Border(bottom=Side(style="medium", color=NAVY))


def _header_row(sheet, row: int, columns: list[str], titles: list[str]) -> None:
    for column, title in zip(columns, titles):
        cell = sheet[f"{column}{row}"]
        cell.value = title
        cell.font = Font(bold=True, color=WHITE)
        cell.fill = _fill(NAVY)
        cell.alignment = CENTER
        cell.border = BORDER
    sheet.row_dimensions[row].height = 24


def _counts(rows: list[ReceiptRow]) -> dict:
    return {status: sum(r.status == status for r in rows) for status in STATUS_STYLES}


# =====================================================================
# Part 1: title banner (rows 1-2)
# =====================================================================
def _add_banner(sheet, rows: list[ReceiptRow]) -> None:
    sheet.merge_cells(f"{FIRST_COL}1:{LAST_COL}1")
    title = sheet[f"{FIRST_COL}1"]
    title.value = "Expense Report"
    title.font = Font(size=20, bold=True, color=WHITE)
    title.fill = _fill(NAVY)
    title.alignment = LEFT
    sheet.row_dimensions[1].height = 40

    sheet.merge_cells(f"{FIRST_COL}2:{LAST_COL}2")
    subtitle = sheet[f"{FIRST_COL}2"]
    subtitle.value = f"Generated on {date.today():%d %B %Y}  ·  {len(rows)} receipt(s) processed"
    subtitle.font = Font(size=11, italic=True, color=WHITE)
    subtitle.fill = _fill(BLUE)
    subtitle.alignment = LEFT
    sheet.row_dimensions[2].height = 22


# =====================================================================
# Part 2: KPI cards (rows 4-5)
# =====================================================================
def _add_kpi_cards(sheet, rows: list[ReceiptRow]) -> None:
    counts = _counts(rows)

    # Last card: total spent in the main (biggest) currency
    groups = _spending_groups(rows)
    if groups:
        currency, items = groups[0]
        spent_label, spent_value = f"Total spent ({currency})", sum(item[2] for item in items)
    else:
        spent_label, spent_value = "Total spent", 0

    cards = [
        ("Receipts", len(rows), BLUE),
        ("Ready", counts["ok"], "2E7D32"),
        ("Needs review", counts["needs_review"], "B26A00"),
        ("Errors", counts["error"], "C62828"),
        (spent_label, spent_value, NAVY),
    ]
    for (first, last), (label, value, color) in zip(CARD_SPANS, cards):
        if first != last:  # a 1-column card needs no merging
            sheet.merge_cells(f"{first}4:{last}4")
            sheet.merge_cells(f"{first}5:{last}5")
        label_cell, value_cell = sheet[f"{first}4"], sheet[f"{first}5"]
        label_cell.value = label.upper()
        label_cell.font = Font(size=9, bold=True, color=TEXT_GREY)
        value_cell.value = value
        value_cell.font = Font(size=24, bold=True, color=color)
        if isinstance(value, float):
            value_cell.number_format = "#,##0.00"

        # Style every cell of the merged card, so fill and borders cover it all
        for column in range(ord(first), ord(last) + 1):
            letter = chr(column)
            top, bottom = sheet[f"{letter}4"], sheet[f"{letter}5"]
            left = THIN if letter == first else None
            right = THIN if letter == last else None
            top.fill = bottom.fill = _fill(LIGHT_GREY)
            top.alignment = bottom.alignment = CENTER
            top.border = Border(top=Side(style="thick", color=color), left=left, right=right)
            bottom.border = Border(bottom=THIN, left=left, right=right)
    sheet.row_dimensions[4].height = 22
    sheet.row_dimensions[5].height = 40


# =====================================================================
# Part 3: spending by category + pie chart (from row 7)
# =====================================================================
def _spending_groups(rows: list[ReceiptRow]) -> list[tuple[str, list[tuple[str, int, float, float]]]]:
    """Group usable rows by currency, then by category.

    Returns [(currency, [(category, receipts, total, tax), ...]), ...]
    Biggest currency first, biggest category first. Currencies are never
    added together, because 100 PKR + 100 USD is meaningless.
    """
    totals: dict[str, dict[str, list]] = {}
    for row in rows:
        if row.status == "error" or row.amount is None:
            continue
        currency = row.currency or "Unknown"
        category = row.category or "Uncategorized"
        entry = totals.setdefault(currency, {}).setdefault(category, [0, 0.0, 0.0])
        entry[0] += 1
        entry[1] += row.amount
        entry[2] += row.tax or 0.0

    groups = []
    for currency, categories in totals.items():
        items = [(cat, n, total, tax) for cat, (n, total, tax) in categories.items()]
        items.sort(key=lambda item: item[2], reverse=True)
        groups.append((currency, items))
    groups.sort(key=lambda group: sum(item[2] for item in group[1]), reverse=True)
    return groups


SPENDING_COLUMNS = ["B", "C", "D", "E", "F", "G"]  # Category, Currency, Receipts, Total, Tax, Share


def _add_spending(sheet, rows: list[ReceiptRow]) -> int:
    """Draws the category table and the pie chart. Returns the next free row."""
    _section_title(sheet, "B7:G7", "Spending by category")
    sheet.row_dimensions[7].height = 26
    _header_row(sheet, 8, SPENDING_COLUMNS, ["Category", "Currency", "Receipts", "Total", "Tax", "Share"])
    row_number = 9
    groups = _spending_groups(rows)

    if not groups:
        sheet.merge_cells(f"B{row_number}:G{row_number}")
        empty = sheet[f"B{row_number}"]
        empty.value = "No usable receipts yet."
        empty.font = Font(italic=True, color=TEXT_GREY)
        empty.alignment = CENTER
        return row_number + 2

    chart_block = None  # (first_row, last_row, categories, currency) of the biggest currency
    for currency, items in groups:
        currency_total = sum(item[2] for item in items)
        first_row = row_number

        for category, receipts, total, tax in items:
            background, text = _category_colors(category)
            values = [category, currency, receipts, total, tax, total / currency_total if currency_total else 0]
            for column, value in zip(SPENDING_COLUMNS, values):
                cell = sheet[f"{column}{row_number}"]
                cell.value = value
                cell.border = BORDER
                cell.alignment = RIGHT
            sheet[f"B{row_number}"].fill = _fill(background)
            sheet[f"B{row_number}"].font = Font(bold=True, color=text)
            sheet[f"B{row_number}"].alignment = LEFT
            sheet[f"C{row_number}"].alignment = CENTER
            sheet[f"D{row_number}"].alignment = CENTER
            sheet[f"E{row_number}"].number_format = "#,##0.00"
            sheet[f"F{row_number}"].number_format = "#,##0.00"
            sheet[f"G{row_number}"].number_format = "0.0%"
            sheet.row_dimensions[row_number].height = 20
            row_number += 1

        # Blue bars inside the "Share" cells
        sheet.conditional_formatting.add(
            f"G{first_row}:G{row_number - 1}",
            DataBarRule(start_type="num", start_value=0, end_type="num", end_value=1, color="5B9BD5"),
        )
        if chart_block is None:
            chart_block = (first_row, row_number - 1, [item[0] for item in items], currency)

        # Subtotal row for this currency
        subtotal = [f"Total {currency}", "", sum(i[1] for i in items), currency_total, sum(i[3] for i in items), 1]
        for column, value in zip(SPENDING_COLUMNS, subtotal):
            cell = sheet[f"{column}{row_number}"]
            cell.value = value
            cell.font = Font(bold=True, color=WHITE)
            cell.fill = _fill(BLUE)
            cell.border = BORDER
            cell.alignment = RIGHT
        sheet[f"B{row_number}"].alignment = LEFT
        sheet[f"D{row_number}"].alignment = CENTER
        sheet[f"E{row_number}"].number_format = "#,##0.00"
        sheet[f"F{row_number}"].number_format = "#,##0.00"
        sheet[f"G{row_number}"].number_format = "0%"
        sheet.row_dimensions[row_number].height = 22
        row_number += 2  # blank line between currencies

    _add_pie_chart(sheet, *chart_block)
    # The next section must start below BOTH the table and the chart
    return max(row_number, 8 + CHART_HEIGHT_ROWS) + 1


def _add_pie_chart(sheet, first_row: int, last_row: int, categories: list[str], currency: str) -> None:
    """Pie chart for the biggest currency, placed to the right of the table."""
    _section_title(sheet, "H7:J7", f"Where the money went ({currency})")

    chart = PieChart()
    chart.auto_title_deleted = True  # the heading above is the title
    chart.add_data(Reference(sheet, min_col=5, min_row=first_row, max_row=last_row), titles_from_data=False)
    chart.set_categories(Reference(sheet, min_col=2, min_row=first_row, max_row=last_row))
    series = chart.series[0]
    for index, category in enumerate(categories):
        point = DataPoint(idx=index)
        point.graphicalProperties.solidFill = _category_colors(category)[1]  # slice = category colour
        point.graphicalProperties.line.solidFill = WHITE
        series.dPt.append(point)

    # Labels show only the percentage (the legend already shows the category)
    chart.dataLabels = DataLabelList()
    chart.dataLabels.showPercent = True
    chart.dataLabels.position = "outEnd"  # outside the slice, so it is easy to read
    for hidden in ("showVal", "showCatName", "showSerName", "showLegendKey"):
        setattr(chart.dataLabels, hidden, False)
    chart.height, chart.width = 9, 12.5
    sheet.add_chart(chart, "H8")


# =====================================================================
# Part 4: all receipts (one row per receipt)
# =====================================================================
def _add_receipts_table(sheet, rows: list[ReceiptRow], start_row: int) -> None:
    _section_title(sheet, f"B{start_row}:J{start_row}", "All receipts")
    sheet.row_dimensions[start_row].height = 26

    note_row = start_row + 1
    sheet.merge_cells(f"B{note_row}:J{note_row}")
    note = sheet[f"B{note_row}"]
    note.value = "Empty cells = not found on the receipt (never guessed).  Use the filter buttons to sort or filter."
    note.font = Font(size=9, italic=True, color=TEXT_GREY)

    header_row = start_row + 2
    _header_row(sheet, header_row, [c[0] for c in RECEIPT_COLUMNS], [c[1] for c in RECEIPT_COLUMNS])

    for index, row in enumerate(rows):
        row_number = header_row + 1 + index
        badge_text, badge_bg, badge_color, row_tint = STATUS_STYLES.get(row.status, STATUS_STYLES["error"])
        # Zebra stripes, unless the row needs attention (then it gets a light tint)
        background = row_tint or (LIGHT_GREY if index % 2 else WHITE)

        for column, _title, attr, _width in RECEIPT_COLUMNS:
            value = getattr(row, attr)
            if attr == "date" and value:
                value = date.fromisoformat(value)  # a real Excel date, not text
            elif attr == "status":
                value = badge_text
            elif isinstance(value, str):
                value = safe_cell(value)

            cell = sheet[f"{column}{row_number}"]
            cell.value = value
            cell.fill = _fill(background)
            cell.border = BORDER
            cell.alignment = LEFT

            if attr == "date":
                cell.number_format = "dd mmm yyyy"
                cell.alignment = CENTER
            elif attr in ("amount", "tax"):
                cell.number_format = "#,##0.00"
                cell.alignment = RIGHT
                if attr == "amount":
                    cell.font = Font(bold=True)
            elif attr == "currency":
                cell.alignment = CENTER
            elif attr == "category" and value:
                category_bg, category_text = _category_colors(value)
                cell.fill = _fill(category_bg)
                cell.font = Font(bold=True, color=category_text)
                cell.alignment = CENTER
            elif attr == "status":
                cell.fill = _fill(badge_bg)
                cell.font = Font(bold=True, color=badge_color)
                cell.alignment = CENTER
            elif attr == "notes":
                cell.font = Font(italic=True, color=TEXT_GREY)
                cell.alignment = Alignment(vertical="center", wrap_text=True, indent=1)
            elif attr == "file":
                cell.font = Font(color=TEXT_GREY)

        # Taller row when a long note has to wrap onto more lines
        note_lines = len(row.notes) // 40 + 1
        sheet.row_dimensions[row_number].height = max(22, 15 * note_lines + 4)

    # Filter buttons on the header row
    last_row = header_row + max(len(rows), 1)
    sheet.auto_filter.ref = f"B{header_row}:J{last_row}"


# =====================================================================
# Public function
# =====================================================================
def rows_to_xlsx(rows: list[ReceiptRow]) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Expense Report"
    sheet.sheet_view.showGridLines = False

    # Column widths (A = small left margin)
    sheet.column_dimensions["A"].width = 3
    for column, _title, _attr, width in RECEIPT_COLUMNS:
        sheet.column_dimensions[column].width = width

    # Build the sheet from top to bottom
    _add_banner(sheet, rows)
    _add_kpi_cards(sheet, rows)
    next_row = _add_spending(sheet, rows)
    _add_receipts_table(sheet, rows, next_row)

    # Print nicely: landscape, fit to one page wide
    sheet.page_setup.orientation = "landscape"
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0
    sheet.sheet_properties.pageSetUpPr.fitToPage = True

    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()
