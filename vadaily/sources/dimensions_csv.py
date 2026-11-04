import csv
import re
from pathlib import Path

from ..records import empty_record
from ..utils import best_date, clean_text, normalize_doi, normalize_pmid, to_number

COLUMN_MAP = {
    "Publication ID": "dimensions_id",
    "DOI": "doi",
    "PMID": "pmid",
    "PMCID": "pmcid",
    "Title": "title",
    "Abstract": "abstract",
    "Acknowledgements": "acknowledgements",
    "Funding": "funding_text",
    "Source title": "journal",
    "Publisher": "publisher",
    "ISSN": "issn",
    "MeSH terms": "mesh_terms",
    "Open Access": "open_access",
    "Retractions & Notices": "retraction",
    "Publication Type": "pub_type",
    "Document Type": "doc_type",
    "Authors": "authors",
    "Corresponding Authors": "corresponding_authors",
    "Authors Affiliations": "affiliations",
    "Research Organizations - standardized": "research_orgs",
    "Funder": "funder",
    "Grant IDs of Supporting Grants": "grant_ids",
    "Times cited": "times_cited",
    "RCR": "rcr",
    "FCR": "fcr",
    "Source Linkout": "source_linkout",
    "RCDC Categories": "rcdc",
    "Health Research Areas": "health_areas",
}


def _find_header(rows):
    for i, row in enumerate(rows[:10]):
        if "Publication ID" in [c.strip() for c in row]:
            return i
    raise ValueError("No header row containing 'Publication ID' found")


def read_file(path):
    """Read one Dimensions CSV export. Returns (records, search_criteria)."""
    with open(path, encoding="utf-8-sig", newline="") as f:
        rows = list(csv.reader(f))
    h = _find_header(rows)
    header = [c.strip() for c in rows[h]]
    idx = {name: i for i, name in enumerate(header)}

    criteria = None
    if h > 0 and rows[0]:
        m = re.search(r"Criteria:\s*(.*?)\.\s", rows[0][0])
        criteria = m.group(1) if m else None

    dim_url_col = next((c for c in header if "Dimensions" in c and c.endswith("URL")), None)
    for_col = next((c for c in header if c.startswith("Fields of Research")), None)

    records = []
    for row in rows[h + 1:]:
        if not any(cell.strip() for cell in row):
            continue

        def get(col):
            i = idx.get(col)
            return row[i].strip() if i is not None and i < len(row) else ""

        rec = empty_record("dimensions")
        for col, field in COLUMN_MAP.items():
            rec[field] = get(col) or None
        rec["dimensions_url"] = get(dim_url_col) or None if dim_url_col else None
        rec["fields_of_research"] = get(for_col) or None if for_col else None
        rec["doi"] = normalize_doi(rec["doi"])
        rec["pmid"] = normalize_pmid(rec["pmid"])
        if rec["issn"]:
            rec["issn"] = rec["issn"].replace(",", ";")
        for f in ("title", "abstract", "funding_text", "acknowledgements"):
            rec[f] = clean_text(rec[f]) or None
        for f in ("times_cited", "rcr", "fcr"):
            rec[f] = to_number(rec[f])
        rec["pub_date"] = best_date(
            get("Publication date (online)"), get("Publication date"),
            get("Publication date (print)"), get("PubYear"),
        )
        records.append(rec)
    return records, criteria


def load_folder(folder):
    """Read every CSV in the folder, newest file first so its values win on merge."""
    folder = Path(folder)
    files = sorted(folder.glob("*.csv"), key=lambda p: p.stat().st_mtime, reverse=True) if folder.exists() else []
    records, info = [], []
    for path in files:
        recs, criteria = read_file(path)
        records.extend(recs)
        info.append({"file": path.name, "rows": len(recs), "criteria": criteria})
    return records, info
