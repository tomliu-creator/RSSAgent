from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from urllib.parse import quote_plus

import feedparser
from googlenewsdecoder import gnewsdecoder

from .models import Candidate


def build_queries(company: dict[str, str], base_query: str | None = None) -> list[str]:
    if base_query:
        return [base_query]
    name = company["company_name"]
    return [
        f"{name} reputation risk",
        f"{name} controversy ESG",
        f"{name} lawsuit fine regulator",
        f"{name} anti-money laundering corruption",
        f"{name} privacy cyber governance",
    ]


def google_news_rss_url(query: str, ceid: str) -> str:
    region, lang = ceid.split(":")
    return (
        "https://news.google.com/rss/search?"
        f"q={quote_plus(query)}&hl={lang}&gl={region}&ceid={ceid}"
    )


def candidate_id(company_id: str, url: str, title: str) -> str:
    raw = f"{company_id}|{url}|{title}".encode("utf-8", errors="ignore")
    return hashlib.sha256(raw).hexdigest()[:16]


def resolve_google_news_url(url: str) -> str:
    if "news.google.com/" not in url:
        return url
    try:
        decoded = gnewsdecoder(url)
        if isinstance(decoded, dict):
            return decoded.get("decoded_url") or decoded.get("url") or url
        if isinstance(decoded, str) and decoded.startswith("http"):
            return decoded
    except Exception:
        return url
    return url


def collect_rss_candidates(
    companies: list[dict[str, str]],
    ceid: str,
    max_items_per_query: int,
    base_query: str | None = None,
) -> list[Candidate]:
    now = datetime.now(timezone.utc).isoformat()
    out: list[Candidate] = []
    seen: set[str] = set()
    for company in companies:
        for query in build_queries(company, base_query):
            url = google_news_rss_url(query, ceid)
            feed = feedparser.parse(url)
            for entry in feed.entries[:max_items_per_query]:
                title = entry.get("title", "")
                link = resolve_google_news_url(entry.get("link", ""))
                cid = candidate_id(company["company_id"], link, title)
                if cid in seen:
                    continue
                seen.add(cid)
                out.append(
                    Candidate(
                        candidate_id=cid,
                        company_id=company["company_id"],
                        company_name=company["company_name"],
                        query=query,
                        title=title,
                        rss_summary=entry.get("summary", ""),
                        url=link,
                        publisher=entry.get("source", {}).get("title", ""),
                        published_at=entry.get("published", ""),
                        collected_at=now,
                    )
                )
    return out
