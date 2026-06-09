from __future__ import annotations

from urllib.parse import urlparse

from .models import Candidate


def _contains_any(text: str, terms: list[str]) -> int:
    low = text.lower()
    return sum(1 for term in terms if term.lower() in low)


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def rank_candidates(
    candidates: list[Candidate],
    policy: dict,
    max_articles: int,
) -> list[Candidate]:
    adverse_terms = policy.get("ranking", {}).get("adverse_terms", [])
    esg_terms = policy.get("ranking", {}).get("esg_terms", [])
    blocked = set(policy.get("download", {}).get("blocked_domains", []))
    allowed = set(policy.get("download", {}).get("allowed_domains", []))

    ranked: list[Candidate] = []
    for candidate in candidates:
        domain = _domain(candidate.url)
        if any(domain == d or domain.endswith("." + d) for d in blocked):
            continue
        if allowed and not any(domain == d or domain.endswith("." + d) for d in allowed):
            continue

        text = f"{candidate.title}\n{candidate.rss_summary}"
        score = 0.0
        score += 4 * _contains_any(text, adverse_terms)
        score += 2 * _contains_any(text, esg_terms)
        if candidate.company_name.lower() in text.lower():
            score += 3
        if candidate.company_id.lower() in text.lower():
            score += 1
        candidate.score = score
        ranked.append(candidate)

    ranked.sort(key=lambda item: item.score, reverse=True)
    return ranked[:max_articles]
