# ESG Controversy Agent MVP Plan

## 1. Current Repo Assessment

### Design document

The high-level design in `Design/esg_controversy_agent_design.md` is directionally right for a corporate environment:

- Build a governed data pipeline, not a free-roaming web agent.
- Start with a small public-company universe and approved public sources.
- Store evidence in an internal search/vector layer.
- Keep the analyst-facing agent separate from ingestion, classification, and indexing.
- Require citations, confidence scores, and human review before investment use.

For the MVP, the strongest design principle is: keep discovery controlled, but allow controlled article retrieval for the top candidate URLs so analysts can inspect evidence and the system can build a local retrieval corpus.

### Existing safe pipeline

`test_pipeline_safe.py` already proves three important things:

- RSS collection works through Google News RSS for a query such as `KKR Reputation Risk`.
- Azure OpenAI access works through Microsoft Entra ID using `ClientSecretCredential`.
- An Azure OpenAI Assistant can classify RSS candidates and return structured JSON.

The script is a useful corporate-environment smoke test, but it is not yet an MVP agent because it:

- Uses a hard-coded query and only the first three RSS items.
- Sends only title, summary, and URL to the model.
- Does not fetch article pages.
- Does not persist raw candidate metadata except one JSON output file.
- Does not embed or index article content.
- Does not deduplicate events.
- Does not have a company master, source whitelist, taxonomy, or analyst review workflow.
- Disables TLS verification to get around corporate SSL inspection. This is okay for a local smoke test only; the MVP should use the corporate CA bundle or approved proxy configuration.

## 2. MVP Goal

Build a local-first ESG controversy monitoring MVP that can run inside the corporate environment with:

- Corporate-approved Azure OpenAI endpoint.
- RSS-based candidate discovery.
- Controlled browsing/downloading of top candidate article links.
- Local article archive in an appropriate format.
- Local vector store for retrieval and evidence search.
- ESG controversy classification, severity, confidence, and citations.
- Analyst review output as JSON/CSV/Markdown.

The MVP should prove the workflow without sending confidential portfolio data into public search or external tools.

## 3. Recommended MVP Architecture

```text
company_universe.csv
        |
        v
RSS query builder
        |
        v
Candidate news collector
        |
        v
Candidate ranker/filter
        |
        v
Top candidate URL browser/downloader
        |
        v
Local article archive
        |
        v
Chunking + embedding
        |
        v
Local vector store
        |
        v
ESG controversy classifier
        |
        v
Event deduplication + scoring
        |
        v
Analyst review files / local dashboard
```

## 4. Local MVP Components

### 4.1 Inputs

Create these local config files:

- `config/company_universe.csv`
  - `company_id`
  - `company_name`
  - `ticker`
  - `country`
  - `sector`
  - `aliases`
  - `subsidiaries`

- `config/source_policy.yaml`
  - allowed RSS sources
  - allowed direct-download domains
  - blocked domains
  - max articles per company per run
  - whether full text can be stored

- `config/esg_taxonomy.yaml`
  - E/S/G pillar
  - category
  - examples
  - severity hints

- `.env`
  - local endpoint and auth settings
  - no secrets committed to git

### 4.2 RSS Candidate Discovery

Extend the existing RSS approach into a controlled collector:

- Generate queries per company:
  - `"{company}" controversy ESG`
  - `"{company}" lawsuit`
  - `"{company}" fine regulator`
  - `"{company}" pollution`
  - `"{company}" labor rights`
  - `"{company}" bribery corruption`
  - `"{company}" data privacy breach`

- Pull from Google News RSS first because the existing script already works.
- Add other approved RSS feeds later.
- Normalize each candidate into:

```json
{
  "candidate_id": "hash",
  "company_id": "MSFT",
  "query": "Microsoft data privacy breach",
  "title": "...",
  "rss_summary": "...",
  "url": "...",
  "publisher": "...",
  "published_at": "...",
  "collected_at": "...",
  "source_type": "rss"
}
```

### 4.3 Candidate Ranking

Before downloading pages, run a cheap filter:

- Keyword score for adverse/ESG terms.
- Company/alias match score.
- Source-domain allowlist check.
- Recency score.
- Optional LLM mini-classification using title and RSS summary only.

Keep the top candidates per company, for example:

- top 5 per company per run for local testing
- top 20 per company per day for expanded MVP

### 4.4 Browse, Download, and Archive Top Candidate News

This is a required MVP feature.

For each top candidate URL:

1. Resolve the RSS redirect to the canonical article URL where possible.
2. Check the domain against `source_policy.yaml`.
3. Download article content using an approved HTTP client.
4. Extract readable content with `trafilatura` or `readability-lxml`.
5. Save both metadata and extracted text locally.
6. If extraction fails, save metadata and mark `download_status = failed`.

Recommended local archive format:

```text
data/
  raw/
    articles/
      YYYY-MM-DD/
        {candidate_id}.json
        {candidate_id}.txt
  processed/
    chunks/
      {candidate_id}.jsonl
  indexes/
    chroma/
  outputs/
    runs/
      {run_id}_candidates.jsonl
      {run_id}_events.json
      {run_id}_analyst_report.md
```

Recommended JSON document:

```json
{
  "candidate_id": "hash",
  "canonical_url": "...",
  "rss_url": "...",
  "title": "...",
  "publisher": "...",
  "published_at": "...",
  "downloaded_at": "...",
  "content_sha256": "...",
  "content_format": "text/plain",
  "full_text_stored": true,
  "license_note": "public web; internal MVP use only",
  "extracted_text": "...",
  "extraction_method": "trafilatura",
  "download_status": "success"
}
```

Corporate note: if compliance does not allow full-text article storage, store only metadata, short snippets, hashes, and generated summaries. Keep the code path configurable.

### 4.5 Local Vector Store

For a local MVP, use Chroma or FAISS:

- Chroma is easier for metadata filtering and persistence.
- FAISS is simple and fast, but metadata handling needs extra code.

Recommended MVP choice: Chroma persisted under `data/indexes/chroma`.

Chunking:

- chunk size: 700-1,000 tokens
- overlap: 100-150 tokens
- metadata on every chunk:
  - `candidate_id`
  - `company_id`
  - `company_name`
  - `publisher`
  - `published_at`
  - `canonical_url`
  - `esg_candidate_score`

Embedding:

- Use Azure OpenAI embedding deployment, preferably `text-embedding-3-small`.
- Store embedding model/deployment name and dimensions in index metadata.

Retrieval:

- Query by company/date/category.
- Retrieve top chunks for classifier evidence.
- Return citations with URL and text spans.

### 4.6 ESG Classification and Event Extraction

Use the Azure LLM endpoint after article download and retrieval.

For each candidate article, ask for structured JSON:

```json
{
  "is_target_company": true,
  "matched_entity": "parent|subsidiary|brand|executive|supplier|uncertain",
  "is_adverse": true,
  "is_esg_controversy": true,
  "esg_pillar": "E|S|G",
  "category": "...",
  "event_type": "...",
  "severity": 1,
  "confidence": 0.0,
  "novelty": "new_event|follow_up|duplicate|uncertain",
  "event_summary": "...",
  "evidence": [
    {
      "source": "...",
      "url": "...",
      "published_at": "...",
      "supporting_text": "..."
    }
  ],
  "reasoning_short": "..."
}
```

### 4.7 Deduplication

Start with pragmatic deduplication:

- Same company.
- Similar event category.
- Article dates within 14-30 days.
- High title/summary embedding similarity.
- LLM confirms whether two candidate events are the same underlying controversy.

Persist event records:

```json
{
  "event_id": "hash",
  "company_id": "...",
  "event_title": "...",
  "first_seen": "...",
  "latest_seen": "...",
  "severity": 3,
  "confidence": 0.82,
  "esg_pillar": "G",
  "category": "Data privacy / cyber governance",
  "article_ids": ["..."],
  "analyst_review_status": "pending"
}
```

## 5. Implementation Phases

### Phase 0 - Corporate Access Smoke Test

Use `test_pipeline_safe.py` as the smoke test:

- Confirm RSS access works behind proxy.
- Confirm Azure OpenAI endpoint works.
- Confirm Assistant ID or chat deployment works.
- Replace TLS-disable workaround with corporate CA bundle if possible.

### Phase 1 - Repo Structure and Config

Add:

- `requirements.txt`
- `.env.example`
- `config/company_universe.csv`
- `config/source_policy.yaml`
- `config/esg_taxonomy.yaml`
- `src/rss_agent/`
- `data/` ignored by git

### Phase 2 - RSS Collector

Build:

- company query builder
- RSS fetcher
- candidate normalizer
- JSONL run output

Output:

- `data/outputs/runs/{run_id}_candidates.jsonl`

### Phase 3 - Candidate Ranking

Build:

- keyword/entity/source scoring
- top candidate selection
- optional title-summary LLM filter

Output:

- `data/outputs/runs/{run_id}_top_candidates.jsonl`

### Phase 4 - Article Browser/Downloader

Build:

- canonical URL resolver
- domain allowlist check
- article downloader
- text extractor
- metadata archive
- failure logging

Output:

- `data/raw/articles/YYYY-MM-DD/{candidate_id}.json`
- `data/raw/articles/YYYY-MM-DD/{candidate_id}.txt`

### Phase 5 - Local Vector Index

Build:

- chunker
- Azure OpenAI embedding client
- Chroma persistent index
- retrieval helper

Output:

- `data/indexes/chroma`

### Phase 6 - ESG Classifier

Build:

- structured prompt
- JSON schema validation with Pydantic
- retry on invalid JSON
- source-cited evidence output

Output:

- `data/outputs/runs/{run_id}_article_classifications.jsonl`

### Phase 7 - Event Builder

Build:

- duplicate detection
- event records
- severity/confidence aggregation
- analyst review report

Output:

- `data/outputs/runs/{run_id}_events.json`
- `data/outputs/runs/{run_id}_analyst_report.md`

### Phase 8 - Analyst Query Interface

Start simple:

- CLI command to ask questions over the local vector store.
- Optional Streamlit app after the pipeline is stable.

Example questions:

- "Show severe new controversies for Microsoft this week."
- "What evidence supports the Tesla labor controversy?"
- "Which governance controversies were found in the last run?"

## 6. Azure OpenAI Endpoint Configuration

The current script expects these variables:

```powershell
$env:AZURE_TENANT_ID="..."
$env:AZURE_CLIENT_ID="..."
$env:AZURE_CLIENT_SECRET="..."
$env:AZURE_OPENAI_ENDPOINT="https://<resource-name>.openai.azure.com/"
$env:AZURE_ASSISTANT_ID="..."
```

For the MVP, also add:

```powershell
$env:AZURE_OPENAI_CHAT_DEPLOYMENT="gpt-4.1-mini"
$env:AZURE_OPENAI_EMBEDDING_DEPLOYMENT="text-embedding-3-small"
$env:AZURE_OPENAI_API_VERSION="2025-04-01-preview"
```

### 6.1 Manual Azure Portal / Foundry Setup

1. Ask IT or your Azure admin for an Azure OpenAI resource in the approved subscription and region.
2. In Azure AI Foundry or Azure OpenAI, deploy:
   - one chat model deployment, for example `gpt-4.1-mini`
   - one embedding deployment, for example `text-embedding-3-small`
3. Create or reuse an Entra ID app registration / service principal for the local MVP.
4. Assign the service principal RBAC access on the Azure OpenAI resource:
   - `Cognitive Services OpenAI User` for inference
   - `Cognitive Services OpenAI Contributor` only if deployment/admin operations are needed
5. Create a client secret and store it in your corporate-approved secret store.
6. Set local environment variables in PowerShell or a local `.env` file.
7. Run the smoke test:

```powershell
cd C:\Users\sunno\Projects\RSSAgent
python test_pipeline_safe.py
```

### 6.2 Azure CLI Setup

Login:

```powershell
az login --tenant "<tenant-id>"
az account set --subscription "<subscription-id>"
```

Create a resource group if needed:

```powershell
az group create `
  --name "<resource-group>" `
  --location "<region>"
```

Create an Azure OpenAI resource if your admin allows local CLI provisioning:

```powershell
az cognitiveservices account create `
  --name "<aoai-resource-name>" `
  --resource-group "<resource-group>" `
  --location "<region>" `
  --kind OpenAI `
  --sku S0 `
  --custom-domain "<aoai-resource-name>"
```

Create a service principal:

```powershell
az ad sp create-for-rbac `
  --name "rssagent-local-mvp" `
  --role "Cognitive Services OpenAI User" `
  --scopes "/subscriptions/<subscription-id>/resourceGroups/<resource-group>/providers/Microsoft.CognitiveServices/accounts/<aoai-resource-name>"
```

Set local environment variables from the returned values:

```powershell
$env:AZURE_TENANT_ID="<tenant>"
$env:AZURE_CLIENT_ID="<appId>"
$env:AZURE_CLIENT_SECRET="<password>"
$env:AZURE_OPENAI_ENDPOINT="https://<aoai-resource-name>.openai.azure.com/"
$env:AZURE_OPENAI_CHAT_DEPLOYMENT="<chat-deployment-name>"
$env:AZURE_OPENAI_EMBEDDING_DEPLOYMENT="<embedding-deployment-name>"
```

For persistent user-level variables:

```powershell
[Environment]::SetEnvironmentVariable("AZURE_TENANT_ID", "<tenant>", "User")
[Environment]::SetEnvironmentVariable("AZURE_CLIENT_ID", "<appId>", "User")
[Environment]::SetEnvironmentVariable("AZURE_CLIENT_SECRET", "<password>", "User")
[Environment]::SetEnvironmentVariable("AZURE_OPENAI_ENDPOINT", "https://<aoai-resource-name>.openai.azure.com/", "User")
```

### 6.3 Preferred Local Auth Pattern

The current service-principal pattern works well for corporate automation. For developer-only testing, a safer keyless pattern is:

```python
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from openai import AzureOpenAI

token_provider = get_bearer_token_provider(
    DefaultAzureCredential(),
    "https://cognitiveservices.azure.com/.default"
)

client = AzureOpenAI(
    azure_endpoint=os.environ["AZURE_OPENAI_ENDPOINT"],
    api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2025-04-01-preview"),
    azure_ad_token_provider=token_provider,
)
```

This avoids storing a client secret locally if your Azure RBAC and device login are approved.

## 7. Python Dependencies

Initial MVP dependencies:

```text
azure-identity
openai
feedparser
requests
httpx
trafilatura
beautifulsoup4
lxml
python-dotenv
pydantic
chromadb
tiktoken
tenacity
pyyaml
pandas
```

Optional:

```text
streamlit
rich
```

## 8. Compliance and Corporate Controls

For the MVP:

- Use public company names only, not confidential holdings or internal ratings.
- Use source allowlists.
- Keep full-text storage configurable.
- Store raw downloaded pages only for internal testing and only when allowed.
- Log every URL fetched.
- Respect blocked domains.
- Do not bypass TLS verification in production code.
- Use managed identity or Entra ID where possible.
- Keep secrets outside git.
- Add human review before any output is used in investment decisions.

## 9. Definition of Done

The MVP is successful when it can:

- Read a 30-50 company universe.
- Generate ESG/adverse-media RSS queries.
- Collect and normalize candidate news.
- Rank top candidate URLs.
- Download and extract the top article links under a source policy.
- Archive article metadata and text locally.
- Chunk and embed the articles.
- Index chunks in a local vector store.
- Classify candidate controversies into an ESG taxonomy.
- Group duplicates into event records.
- Produce a cited analyst report with severity and confidence.
- Run fully from a corporate machine using the approved Azure OpenAI endpoint.

## 10. Suggested Next Build Order

1. Add repo scaffolding and config files.
2. Refactor `test_pipeline_safe.py` into reusable Azure auth and RSS modules.
3. Build the RSS collector and candidate normalizer.
4. Build the top-candidate downloader and archive.
5. Add Chroma vector indexing with Azure embeddings.
6. Add ESG classification with structured JSON validation.
7. Add event deduplication and analyst report generation.
8. Add a simple CLI query interface.
