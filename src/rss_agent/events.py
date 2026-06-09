from __future__ import annotations

import hashlib
from typing import Any

from .models import Classification


def _event_id(row: dict[str, Any]) -> str:
    raw = "|".join(
        [
            str(row.get("company_id", "")),
            str(row.get("esg_pillar", "")),
            str(row.get("category", "")),
            str(row.get("event_type", "")),
            str(row.get("summary", ""))[:80],
        ]
    )
    return hashlib.sha256(raw.encode("utf-8", errors="ignore")).hexdigest()[:16]


def build_events(classifications: list[Classification]) -> list[dict[str, Any]]:
    events: dict[str, dict[str, Any]] = {}
    for classification in classifications:
        row = classification.to_dict()
        if row.get("classification") != "Adverse" and not row.get("is_esg_controversy"):
            continue
        eid = _event_id(row)
        event = events.setdefault(
            eid,
            {
                "event_id": eid,
                "company_id": row.get("company_id"),
                "event_title": row.get("event_type") or row.get("title"),
                "esg_pillar": row.get("esg_pillar"),
                "category": row.get("category"),
                "severity": row.get("severity"),
                "confidence": row.get("confidence"),
                "risk": row.get("risk"),
                "summary": row.get("summary"),
                "article_ids": [],
                "sources": [],
                "analyst_review_status": "pending",
            },
        )
        event["article_ids"].append(row.get("candidate_id"))
        event["sources"].append({"title": row.get("title"), "url": row.get("url")})
    return list(events.values())


def render_report(events: list[dict[str, Any]], classifications: list[Classification]) -> str:
    lines = ["# ESG Controversy MVP Run Report", ""]
    lines.append(f"Candidate classifications: {len(classifications)}")
    lines.append(f"Candidate events: {len(events)}")
    lines.append("")
    for event in events:
        lines.append(f"## {event['event_title']}")
        lines.append(f"- Company: {event['company_id']}")
        lines.append(f"- ESG: {event.get('esg_pillar')} / {event.get('category')}")
        lines.append(f"- Severity: {event.get('severity')} | Confidence: {event.get('confidence')} | Risk: {event.get('risk')}")
        lines.append(f"- Summary: {event.get('summary')}")
        for source in event.get("sources", []):
            lines.append(f"- Source: [{source.get('title')}]({source.get('url')})")
        lines.append("")
    if not events:
        lines.append("No adverse ESG controversy candidates were found in this run.")
    return "\n".join(lines)
