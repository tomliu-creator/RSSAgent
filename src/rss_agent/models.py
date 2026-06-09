from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class Candidate:
    candidate_id: str
    company_id: str
    company_name: str
    query: str
    title: str
    rss_summary: str
    url: str
    publisher: str
    published_at: str
    collected_at: str
    score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return dict(self.__dict__)


@dataclass
class Article:
    candidate: Candidate
    canonical_url: str
    downloaded_at: str
    content_sha256: str
    extracted_text: str
    extraction_method: str
    download_status: str
    error: str = ""

    def to_dict(self) -> dict[str, Any]:
        data = self.candidate.to_dict()
        data.update(
            {
                "canonical_url": self.canonical_url,
                "downloaded_at": self.downloaded_at,
                "content_sha256": self.content_sha256,
                "extracted_text": self.extracted_text,
                "extraction_method": self.extraction_method,
                "download_status": self.download_status,
                "error": self.error,
            }
        )
        return data


@dataclass
class Classification:
    candidate_id: str
    company_id: str
    title: str
    url: str
    result: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = {
            "candidate_id": self.candidate_id,
            "company_id": self.company_id,
            "title": self.title,
            "url": self.url,
        }
        data.update(self.result)
        return data
