from __future__ import annotations

import hashlib
import ssl
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

import httpx
import trafilatura
import truststore
from bs4 import BeautifulSoup

from .io_utils import write_json, write_text
from .models import Article, Candidate


def _extract_text(html: str, url: str) -> tuple[str, str]:
    text = trafilatura.extract(html, url=url, include_comments=False, include_tables=False)
    if text and text.strip():
        return text.strip(), "trafilatura"
    soup = BeautifulSoup(html, "lxml")
    for tag in soup(["script", "style", "noscript"]):
        tag.decompose()
    return soup.get_text("\n", strip=True), "beautifulsoup"


def _is_consent_page(url: str, text: str) -> bool:
    domain = urlparse(url).netloc.lower()
    return domain.endswith("consent.google.com") or text.startswith("Before you continue to Google")


def download_article(candidate: Candidate, out_dir: Path, store_full_text: bool = True) -> Article:
    now = datetime.now(timezone.utc).isoformat()
    try:
        with httpx.Client(
            follow_redirects=True,
            timeout=30,
            verify=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT),
            headers={"User-Agent": "RSSAgentMVP/0.1"},
        ) as client:
            response = client.get(candidate.url)
            response.raise_for_status()
        canonical_url = str(response.url)
        text, method = _extract_text(response.text, canonical_url)
        if _is_consent_page(canonical_url, text):
            text = ""
            method = "blocked_by_consent"
            status = "metadata_only"
        else:
            status = "success" if text else "empty"
        digest = hashlib.sha256(text.encode("utf-8", errors="ignore")).hexdigest()
        article = Article(
            candidate=candidate,
            canonical_url=canonical_url,
            downloaded_at=now,
            content_sha256=digest,
            extracted_text=text if store_full_text else "",
            extraction_method=method,
            download_status=status,
        )
    except Exception as exc:
        article = Article(
            candidate=candidate,
            canonical_url=candidate.url,
            downloaded_at=now,
            content_sha256="",
            extracted_text="",
            extraction_method="none",
            download_status="failed",
            error=str(exc),
        )

    day_dir = out_dir / now[:10]
    write_json(day_dir / f"{candidate.candidate_id}.json", article.to_dict())
    if article.extracted_text:
        write_text(day_dir / f"{candidate.candidate_id}.txt", article.extracted_text)
    return article
