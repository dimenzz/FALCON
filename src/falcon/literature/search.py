from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlencode
from urllib.request import urlopen
import json
import xml.etree.ElementTree as ET


@dataclass(frozen=True)
class LiteratureRecord:
    source: str
    title: str
    abstract: str | None = None
    pmid: str | None = None
    doi: str | None = None
    url: str | None = None
    year: str | None = None
    sources: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.sources:
            object.__setattr__(self, "sources", (self.source,))

    def to_dict(self) -> dict[str, object]:
        return {
            "sources": list(self.sources),
            "title": self.title,
            "abstract": self.abstract,
            "pmid": self.pmid,
            "doi": self.doi,
            "url": self.url,
            "year": self.year,
        }


class LiteratureClient(Protocol):
    def search(self, query: str, max_results: int) -> list[LiteratureRecord]:
        ...


class StaticLiteratureClient:
    def __init__(self, records: list[LiteratureRecord] | None = None) -> None:
        self.records = records or []

    def search(self, query: str, max_results: int) -> list[LiteratureRecord]:
        return self.records[: int(max_results)]


class DualLiteratureClient:
    def __init__(self) -> None:
        self.europe_pmc = EuropePmcClient()
        self.pubmed = PubMedClient()

    def search(self, query: str, max_results: int) -> list[LiteratureRecord]:
        return merge_literature_results(
            self.europe_pmc.search(query, max_results),
            self.pubmed.search(query, max_results),
        )[: int(max_results) * 2]


class EuropePmcClient:
    endpoint = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

    def search(self, query: str, max_results: int) -> list[LiteratureRecord]:
        params = urlencode({"query": query, "format": "json", "pageSize": str(max_results)})
        with urlopen(f"{self.endpoint}?{params}", timeout=20) as response:
            payload = json.loads(response.read().decode("utf-8"))
        records = []
        for item in payload.get("resultList", {}).get("result", []):
            records.append(
                LiteratureRecord(
                    source="europe_pmc",
                    title=item.get("title") or "",
                    abstract=item.get("abstractText"),
                    pmid=item.get("pmid"),
                    doi=item.get("doi"),
                    url=item.get("fullTextUrlList", {}).get("fullTextUrl", [{}])[0].get("url")
                    if item.get("fullTextUrlList")
                    else None,
                    year=item.get("pubYear"),
                )
            )
        return [record for record in records if record.title]


class PubMedClient:
    search_endpoint = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
    fetch_endpoint = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"

    def search(self, query: str, max_results: int) -> list[LiteratureRecord]:
        search_params = urlencode(
            {"db": "pubmed", "term": query, "retmode": "json", "retmax": str(max_results)}
        )
        with urlopen(f"{self.search_endpoint}?{search_params}", timeout=20) as response:
            search_payload = json.loads(response.read().decode("utf-8"))
        ids = search_payload.get("esearchresult", {}).get("idlist", [])
        if not ids:
            return []
        fetch_params = urlencode({"db": "pubmed", "id": ",".join(ids), "retmode": "xml"})
        with urlopen(f"{self.fetch_endpoint}?{fetch_params}", timeout=20) as response:
            root = ET.fromstring(response.read())
        records = []
        for article in root.findall(".//PubmedArticle"):
            pmid = article.findtext(".//PMID")
            title = "".join(article.findtext(".//ArticleTitle") or "").strip()
            abstract = " ".join(text.text or "" for text in article.findall(".//AbstractText")).strip() or None
            doi = None
            for article_id in article.findall(".//ArticleId"):
                if article_id.attrib.get("IdType") == "doi":
                    doi = article_id.text
            records.append(
                LiteratureRecord(
                    source="pubmed",
                    title=title,
                    abstract=abstract,
                    pmid=pmid,
                    doi=doi,
                    url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None,
                    year=article.findtext(".//PubDate/Year"),
                )
            )
        return [record for record in records if record.title]


def merge_literature_results(
    europe_pmc_records: list[LiteratureRecord],
    pubmed_records: list[LiteratureRecord],
) -> list[LiteratureRecord]:
    merged: dict[str, LiteratureRecord] = {}
    order: list[str] = []
    for record in [*europe_pmc_records, *pubmed_records]:
        key = _record_key(record)
        if key not in merged:
            merged[key] = record
            order.append(key)
            continue
        existing = merged[key]
        sources = tuple(dict.fromkeys([*existing.sources, *record.sources]))
        merged[key] = LiteratureRecord(
            source=existing.source,
            sources=sources,
            title=existing.title or record.title,
            abstract=existing.abstract or record.abstract,
            pmid=existing.pmid or record.pmid,
            doi=existing.doi or record.doi,
            url=existing.url or record.url,
            year=existing.year or record.year,
        )
    return [merged[key] for key in order]


def _record_key(record: LiteratureRecord) -> str:
    if record.pmid:
        return f"pmid:{record.pmid.strip().lower()}"
    if record.doi:
        return f"doi:{record.doi.strip().lower()}"
    return f"title:{' '.join(record.title.lower().split())}"
