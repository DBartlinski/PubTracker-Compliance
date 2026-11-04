import csv
import io
from datetime import datetime
from pathlib import Path

from fpdf import FPDF
from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

COLUMNS = [
    ("Newsworthiness", "tier"), ("Score", "score"), ("Added", "added"), ("Publication date", "pub_date"),
    ("Title", "title"), ("Journal", "journal"), ("Journal tier", "journal_tier"),
    ("Publication type", "pub_type"), ("Document type", "doc_type"),
    ("VA affiliated", "va_affiliated"), ("VA funded", "va_funded"), ("ORD funded", "ord_funded"),
    ("ORD services", "ord_services"), ("Funding evidence", "funding_evidence"), ("Score reasons", "score_reasons"),
    ("Authors", "authors"), ("Corresponding authors", "corresponding_authors"), ("DOI", "doi"), ("PMID", "pmid"),
    ("PMCID", "pmcid"), ("Dimensions URL", "dimensions_url"), ("DOI URL", "doi_url"), ("PubMed URL", "pubmed_url"),
    ("Open access URL", "oa_url"), ("Publisher link", "source_linkout"), ("Sources", "sources"),
    ("Retraction / notice", "retraction"), ("First seen", "first_seen"),
]
URL_FIELDS = {"dimensions_url", "doi_url", "pubmed_url", "oa_url", "source_linkout"}
EXCEL_CELL_LIMIT = 32000
_UNICODE_FONTS = [Path(r"C:\Windows\Fonts\arial.ttf"), Path(r"C:\Windows\Fonts\arialbd.ttf")]
# Arial lacks these hyphen variants.
_PDF_CHARS = str.maketrans({"\u2010": "-", "\u2011": "-", "\u2012": "-"})


def _links(r):
    return {
        "doi_url": f"https://doi.org/{r['doi']}" if r.get("doi") else None,
        "pubmed_url": f"https://pubmed.ncbi.nlm.nih.gov/{r['pmid']}/" if r.get("pmid") else None,
    }


def _value(r, field):
    v = _links(r).get(field) if field in ("doi_url", "pubmed_url") else r.get(field)
    if field == "funding_evidence":
        return " | ".join(f"{e['label']} [{e['source']}]: {e['snippet']}" for e in v or [])
    if isinstance(v, bool):
        return "Yes" if v else "No"
    if isinstance(v, list):
        return "; ".join(str(x) for x in v)
    return v


def _safe(v):
    # Stop spreadsheet apps from treating text as a formula.
    if isinstance(v, str) and v[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + v
    return v


def rows(records):
    return [[_safe(_value(r, f)) for _, f in COLUMNS] for r in records]


def to_csv(records):
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([h for h, _ in COLUMNS])
    w.writerows(rows(records))
    return buf.getvalue().encode("utf-8-sig")


def to_xlsx(records):
    wb = Workbook()
    ws = wb.active
    ws.title = "Publications"
    ws.append([h for h, _ in COLUMNS])
    for cell in ws[1]:
        cell.font = Font(bold=True)
    for r, values in zip(records, rows(records)):
        ws.append([v[:EXCEL_CELL_LIMIT] if isinstance(v, str) else v for v in values])
        row = ws.max_row
        for col, (_, field) in enumerate(COLUMNS, 1):
            cell = ws.cell(row=row, column=col)
            if field in URL_FIELDS and isinstance(cell.value, str) and cell.value.startswith("http"):
                cell.hyperlink = cell.value
                cell.style = "Hyperlink"
    widths = {"title": 70, "journal": 30, "funding_evidence": 60, "score_reasons": 45, "authors": 40}
    for col, (_, field) in enumerate(COLUMNS, 1):
        ws.column_dimensions[get_column_letter(col)].width = widths.get(field, 16)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


class _Digest(FPDF):
    def footer(self):
        self.set_y(-12)
        self.set_font(self.base_font, size=8)
        self.cell(0, 8, f"Page {self.page_no()}", align="C")


def to_pdf(records, title="VA Research Daily Digest"):
    pdf = _Digest(format="Letter")
    unicode_ok = all(p.exists() for p in _UNICODE_FONTS)
    if unicode_ok:
        pdf.add_font("ArialU", "", str(_UNICODE_FONTS[0]))
        pdf.add_font("ArialU", "B", str(_UNICODE_FONTS[1]))
        pdf.base_font = "ArialU"
    else:
        pdf.base_font = "Helvetica"

    def t(s):
        s = str(s or "").translate(_PDF_CHARS)
        return s if unicode_ok else s.encode("latin-1", "replace").decode("latin-1")

    def para(text, size=9, style="", h=4.6):
        pdf.set_font(pdf.base_font, style, size)
        pdf.multi_cell(0, h, t(text), new_x="LMARGIN", new_y="NEXT")

    pdf.set_auto_page_break(True, margin=15)
    pdf.add_page()
    para(title, size=16, style="B", h=8)
    tiers = {k: sum(1 for r in records if r.get("tier") == k) for k in ("High", "Medium", "Low")}
    para(f"Generated {datetime.now():%Y-%m-%d %H:%M} | {len(records)} publications | "
         f"High {tiers['High']} | Medium {tiers['Medium']} | Low {tiers['Low']}", size=9)
    pdf.ln(3)

    for tier in ("High", "Medium", "Low"):
        group = [r for r in records if r.get("tier") == tier]
        if not group:
            continue
        para(f"{tier} newsworthiness ({len(group)})", size=13, style="B", h=7)
        pdf.ln(1)
        for r in group:
            _pdf_entry(pdf, r, para, t)
    return bytes(pdf.output())


def _pdf_entry(pdf, r, para, t):
    preprint = "PREPRINT (not peer reviewed) - " if r.get("journal_tier") == "Preprint" else ""
    para(f"[{r.get('score')}] {preprint}{r.get('title') or '(untitled)'}", size=10, style="B", h=5)
    jt = r.get("journal_tier")
    meta = " | ".join(filter(None, [
        r.get("journal"), f"{jt} journal" if jt in ("Top", "Mid", "Lower") else None,
        f"Published {r.get('pub_date')}", f"Added {r.get('added')}", r.get("doc_type") or r.get("pub_type")]))
    para(meta)
    funding = "ORD: " + ", ".join(r["ord_services"]) if r.get("ord_funded") else (
        "VA funded" if r.get("va_funded") else "No VA funding identified")
    para(funding + (" | VA affiliated" if r.get("va_affiliated") else ""))
    if r.get("score_reasons"):
        para("Why: " + "; ".join(r["score_reasons"]), size=8)
    links = _links(r)
    for label, url in (("DOI", links["doi_url"]), ("PubMed", links["pubmed_url"]),
                       ("Dimensions", r.get("dimensions_url"))):
        if url:
            pdf.set_font(pdf.base_font, "", 8)
            pdf.set_text_color(0, 70, 160)
            pdf.write(4.2, t(f"{label}: {url}"), link=url)
            pdf.set_text_color(0, 0, 0)
            pdf.ln(4.2)
    pdf.ln(2.5)


FORMATS = {
    "csv": (to_csv, "text/csv", "csv"),
    "xlsx": (to_xlsx, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", "xlsx"),
    "pdf": (to_pdf, "application/pdf", "pdf"),
}
