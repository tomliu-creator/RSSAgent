# RSSAgent

Local ESG controversy monitoring MVP for a corporate Azure environment.

The MVP uses:

- Google News RSS for controlled candidate discovery.
- Google News URL decoding to reach publisher URLs where possible.
- Local article download and text extraction.
- Azure OpenAI with Microsoft Entra ID / Azure CLI auth only.
- Azure OpenAI embeddings.
- Local Chroma vector store under `data/indexes/chroma`.
- Assistant-based ESG controversy classification.
- Local JSONL, JSON, and Markdown run outputs.

No OpenAI API key, Azure OpenAI key, or client secret is required.

## Setup

```powershell
cd C:\Users\sunno\Projects\RSSAgent
az login --tenant 9692a3d3-2a08-4ec8-a0bd-1db355eb4230
python -m pip install --user -e .
```

The local `.env.local` file contains non-secret Azure endpoint/deployment IDs. It is intentionally ignored by git.

## Run

```powershell
python -m rss_agent.cli run --company-id APG --query "APG Asset Management Reputation Risk" --max-items 3 --reset-index
```

Outputs are written to:

```text
data/outputs/runs/
data/raw/articles/
data/processed/chunks/
data/indexes/chroma/
```

## Query The Local Evidence Index

```powershell
python -m rss_agent.cli ask "APG anti money laundering Nepal" --top-k 2
```

## Smoke Test

The original `test_pipeline_safe.py` is still available as a minimal RSS + Azure Assistant connectivity test.
