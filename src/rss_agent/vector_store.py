from __future__ import annotations

from pathlib import Path
from typing import Any

from bs4 import BeautifulSoup
import chromadb
import tiktoken
from chromadb.config import Settings

from .azure_client import build_azure_openai_client
from .config import env
from .io_utils import write_jsonl
from .models import Article


def chunk_text(text: str, chunk_tokens: int = 800, overlap: int = 120) -> list[str]:
    encoding = tiktoken.get_encoding("cl100k_base")
    tokens = encoding.encode(text)
    chunks: list[str] = []
    start = 0
    while start < len(tokens):
        end = min(start + chunk_tokens, len(tokens))
        chunks.append(encoding.decode(tokens[start:end]))
        if end == len(tokens):
            break
        start = max(0, end - overlap)
    return chunks


def evidence_text(article: Article) -> str:
    if article.extracted_text:
        return article.extracted_text
    soup = BeautifulSoup(article.candidate.rss_summary or "", "lxml")
    snippet = soup.get_text(" ", strip=True)
    return "\n".join(
        part
        for part in [
            f"Title: {article.candidate.title}",
            f"Publisher: {article.candidate.publisher}",
            f"Published: {article.candidate.published_at}",
            f"RSS snippet: {snippet}",
            f"URL: {article.candidate.url}",
        ]
        if part.strip()
    )


class LocalVectorStore:
    def __init__(
        self,
        persist_dir: Path,
        collection: str = "esg_controversy_evidence",
        reset: bool = False,
    ):
        persist_dir.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=str(persist_dir),
            settings=Settings(anonymized_telemetry=False),
        )
        if reset:
            try:
                self.client.delete_collection(collection)
            except Exception:
                pass
        self.collection = self.client.get_or_create_collection(collection)
        self.aoai = build_azure_openai_client()
        self.embedding_deployment = env("AZURE_OPENAI_EMBEDDING_DEPLOYMENT", "text-embedding-3-large")

    def embed(self, texts: list[str]) -> list[list[float]]:
        response = self.aoai.embeddings.create(model=self.embedding_deployment, input=texts)
        return [item.embedding for item in response.data]

    def add_articles(self, articles: list[Article], chunks_path: Path) -> int:
        docs: list[str] = []
        ids: list[str] = []
        metadatas: list[dict[str, Any]] = []
        chunk_rows: list[dict[str, Any]] = []
        for article in articles:
            text = evidence_text(article)
            if not text:
                continue
            for i, chunk in enumerate(chunk_text(text)):
                doc_id = f"{article.candidate.candidate_id}-{i}"
                meta = {
                    "candidate_id": article.candidate.candidate_id,
                    "company_id": article.candidate.company_id,
                    "company_name": article.candidate.company_name,
                    "title": article.candidate.title,
                    "publisher": article.candidate.publisher,
                    "published_at": article.candidate.published_at,
                    "canonical_url": article.canonical_url,
                    "score": article.candidate.score,
                }
                ids.append(doc_id)
                docs.append(chunk)
                metadatas.append(meta)
                chunk_rows.append({"id": doc_id, "text": chunk, "metadata": meta})
        if not docs:
            return 0
        embeddings = self.embed(docs)
        self.collection.upsert(ids=ids, documents=docs, metadatas=metadatas, embeddings=embeddings)
        write_jsonl(chunks_path, chunk_rows)
        return len(docs)

    def query(self, text: str, top_k: int = 5) -> list[dict[str, Any]]:
        embedding = self.embed([text])[0]
        result = self.collection.query(
            query_embeddings=[embedding],
            n_results=top_k,
            include=["documents", "metadatas", "distances"],
        )
        return [
            {"text": doc, "metadata": meta, "distance": dist}
            for doc, meta, dist in zip(
                result["documents"][0],
                result["metadatas"][0],
                result["distances"][0],
            )
        ]
