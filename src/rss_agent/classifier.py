from __future__ import annotations

import json
import time
from typing import Any

from bs4 import BeautifulSoup

from .azure_client import build_azure_openai_client
from .config import env
from .models import Article, Classification


INSTRUCTIONS = """Classify this news article as an ESG controversy candidate.
Return ONLY a JSON object with these fields:
{
  "is_target_company": true/false,
  "matched_entity": "parent|subsidiary|brand|executive|supplier|uncertain",
  "classification": "Adverse or Not Adverse",
  "is_esg_controversy": true/false,
  "esg_pillar": "E|S|G|None",
  "category": "controlled ESG category or None",
  "event_type": "short event type",
  "severity": 1-5,
  "confidence": 0.0-1.0,
  "novelty": "new_event|follow_up|duplicate|uncertain",
  "publisher": "publisher",
  "summary": "short evidence-based summary",
  "explanation": "short explanation",
  "risk": "low|medium|high"
}
Do not classify neutral business updates as ESG controversies."""


def parse_json(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return json.loads(text)


class AssistantClassifier:
    def __init__(self):
        self.client = build_azure_openai_client()
        self.assistant_id = env("AZURE_ASSISTANT_ID")
        if not self.assistant_id:
            raise RuntimeError("AZURE_ASSISTANT_ID is required for keyless Assistant classification.")

    def _call(self, payload: str) -> str:
        thread = self.client.beta.threads.create()
        self.client.beta.threads.messages.create(
            thread_id=thread.id,
            role="user",
            content=INSTRUCTIONS + "\n\n" + payload,
        )
        run = self.client.beta.threads.runs.create(
            thread_id=thread.id,
            assistant_id=self.assistant_id,
        )
        while run.status in {"queued", "in_progress", "cancelling"}:
            time.sleep(1)
            run = self.client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
        if run.status != "completed":
            raise RuntimeError(f"Assistant run failed with status {run.status}")
        messages = self.client.beta.threads.messages.list(thread_id=thread.id)
        return messages.data[0].content[0].text.value.strip()

    def classify(self, article: Article) -> Classification:
        if article.extracted_text:
            text = article.extracted_text[:8000]
        else:
            text = BeautifulSoup(article.candidate.rss_summary or "", "lxml").get_text(" ", strip=True)
        payload = f"""Company: {article.candidate.company_name}
Title: {article.candidate.title}
Publisher: {article.candidate.publisher}
Published: {article.candidate.published_at}
URL: {article.canonical_url}
RSS summary: {article.candidate.rss_summary}
Article text:
{text}
"""
        raw = self._call(payload)
        try:
            result = parse_json(raw)
        except Exception:
            result = {
                "classification": "Parse error",
                "is_esg_controversy": False,
                "risk": "unknown",
                "explanation": "Model did not return parseable JSON.",
                "raw_response": raw,
            }
        return Classification(
            candidate_id=article.candidate.candidate_id,
            company_id=article.candidate.company_id,
            title=article.candidate.title,
            url=article.canonical_url,
            result=result,
        )
