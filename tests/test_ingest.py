from vadaily.records import group_records, merge_records
from vadaily.sources.dimensions_csv import read_file
from vadaily.utils import best_date, normalize_doi

HEADER = ("Rank,Publication ID,DOI,PMID,Title,Abstract,Funding,Publication date,PubYear,"
          "Publication date (online),Publication date (print),Funder,Grant IDs of Supporting Grants,"
          "Dimensions for Veterans Affairs URL,Fields of Research (ANZSRC 2020)")


def test_read_dimensions_export_with_preamble_and_multiline(tmp_path):
    p = tmp_path / "export.csv"
    p.write_text(
        '"About the data: Exported on Nov 04, 2026. Criteria: Publication Year is 2027 or 2026.  Note: x",,,\n'
        + HEADER + "\n"
        + '100,pub.1,10.1/ABC,123,"A title","Line one\nLine two",Funded by VA &amp; NIH,2026-12,2026,2026-10-29,,'
          'Department of Veterans Affairs,I01BX000001,https://va.dimensions.ai/details/publication/pub.1,32 Biomedical\n',
        encoding="utf-8",
    )
    records, criteria = read_file(p)
    assert criteria == "Publication Year is 2027 or 2026"
    assert len(records) == 1
    r = records[0]
    assert r["dimensions_id"] == "pub.1"
    assert r["doi"] == "10.1/abc"
    assert r["abstract"] == "Line one\nLine two"
    assert r["funding_text"] == "Funded by VA & NIH"
    assert r["pub_date"] == "2026-10-29"
    assert r["dimensions_url"].endswith("pub.1")
    assert r["fields_of_research"] == "32 Biomedical"


def test_best_date_prefers_first_day_precise():
    assert best_date("", "2027-01", "2026-12-15") == "2026-12-15"
    assert best_date("2026-10-29", "2027-01") == "2026-10-29"
    assert best_date(None, "2026-11", "2026") == "2026-11-01"


def test_normalize_doi():
    assert normalize_doi("https://doi.org/10.1000/XYZ") == "10.1000/xyz"


def test_merge_by_doi_and_pmid_with_dimensions_priority():
    dims = {"sources": ["dimensions"], "doi": "10.1/a", "pmid": None, "title": "Dims title",
            "funder": "VA", "first_seen": "2026-11-04T09:00:00"}
    pm = {"sources": ["pubmed"], "doi": "10.1/a", "pmid": "55", "title": "PubMed title",
          "funder": "BLRD VA", "mesh_terms": "Veterans", "first_seen": "2026-11-05T09:00:00"}
    oa = {"sources": ["openalex"], "doi": None, "pmid": "55", "oa_url": "https://x", "first_seen": "2026-11-05T09:00:00"}
    other = {"sources": ["openalex"], "doi": "10.9/z", "title": "Other"}
    groups = group_records([pm, oa, dims, other])
    assert len(groups) == 2
    merged = merge_records(next(g for g in groups if len(g) == 3))
    assert merged["title"] == "Dims title"
    assert merged["pmid"] == "55"
    assert merged["oa_url"] == "https://x"
    assert merged["funder"] == "VA; BLRD VA"
    assert merged["sources"] == ["dimensions", "pubmed", "openalex"]
    assert merged["first_seen"] == "2026-11-04T09:00:00"


def test_pubmed_future_issue_date_falls_back_to_entrez_date():
    import xml.etree.ElementTree as ET
    from vadaily.sources.pubmed import parse_article

    xml = ("<PubmedArticle><MedlineCitation><PMID>1</PMID><Article><ArticleTitle>T</ArticleTitle>"
           "<Journal><JournalIssue><PubDate><Year>2026</Year><Month>Dec</Month></PubDate></JournalIssue>"
           "<Title>J</Title></Journal></Article></MedlineCitation><PubmedData><History>"
           "<PubMedPubDate PubStatus='pubmed'><Year>2026</Year><Month>11</Month><Day>9</Day></PubMedPubDate>"
           "</History></PubmedData></PubmedArticle>")
    assert parse_article(ET.fromstring(xml))["pub_date"] == "2026-11-09"


def test_merge_keeps_va_trusted_if_any_piece_is_trusted():
    a = {"sources": ["pubmed"], "doi": "10.1/t", "va_trusted": False}
    b = {"sources": ["openalex"], "doi": "10.1/t", "va_trusted": True}
    assert merge_records([a, b])["va_trusted"] is True
