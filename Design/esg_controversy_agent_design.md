# ESG Controversy Agent — Enterprise Design Notes

**Context:** Build an enterprise ESG controversy agent in Microsoft / Azure Foundry that scans public information for negative ESG news around a company universe, for example the S&P 500 or an internal portfolio list.

**Main design view:** Do not build this as a free-roaming web-browsing agent. Build it as a governed **data pipeline + evidence store + analyst-facing agent**. The agent should not be responsible for randomly searching the internet for 500 companies by itself. The agent should sit on top of a controlled data layer that collects, filters, deduplicates, classifies, stores, and cites evidence.

---

## 1. Target Outcome

The system should answer questions such as:

- What new ESG controversies appeared today for my watchlist?
- Which portfolio companies had severe negative ESG news this week?
- Is this article a new controversy or just a follow-up to an existing event?
- Which companies have repeated labor, governance, privacy, corruption, or environmental issues?
- Show the evidence, source, date, severity, and confidence for each controversy.

The output should be **event-centric**, not article-centric. Portfolio managers and analysts care about controversy events, not every duplicated media article.

---

## 2. Recommended Architecture

```text
Company universe / portfolio list
        ↓
Company master and entity resolver
        ↓
Scheduled data collection
        ↓
Approved public sources / licensed news / regulatory sources / selected web search
        ↓
Raw article and source metadata store
        ↓
Deduplication + entity matching + ESG taxonomy classification
        ↓
Severity, novelty, confidence, and materiality scoring
        ↓
Internal ESG controversy event database
        ↓
Azure AI Search index
        ↓
Microsoft Foundry agent
        ↓
Analyst UI: Foundry playground, Teams, internal web app, Power BI, email alert
```

### Preferred Azure / Microsoft components

| Layer | Suggested Tool | Role |
|---|---|---|
| Agent interface | Microsoft Foundry Agent Service | Analyst-facing ESG controversy assistant |
| Public web grounding | Foundry Web Search Tool | Ad hoc public web investigation and current information grounding |
| Controlled web grounding | Grounding with Bing Custom Search | Search only approved public domains, where available |
| Evidence retrieval | Azure AI Search | Internal searchable controversy store with hybrid keyword/vector retrieval |
| Storage | ADLS Gen2 or Blob Storage | Store raw articles, snapshots, metadata, and model outputs |
| Metadata / event database | Azure SQL, PostgreSQL, or Cosmos DB | Store event IDs, company IDs, scores, review status, and history |
| Orchestration | Azure Functions, Durable Functions, Logic Apps, or Data Factory | Scheduled scan and ingestion jobs |
| Secrets and identity | Key Vault + Managed Identity | Avoid storing API keys in code |
| Monitoring | Application Insights / Azure Monitor | Track cost, latency, errors, tool calls, and pipeline failures |
| Evaluation | Foundry Evaluations + custom labeled dataset | Measure retrieval, classification, and summary quality |

---

## 3. Data Strategy — Most Important Part

The data strategy is more important than the LLM prompt. A controversy agent is only useful if it has the right source universe, a strong entity-matching layer, and a reliable definition of what counts as an ESG controversy.

### 3.1 Data categories

| Data Type | Examples | Value | Compliance / Risk Consideration |
|---|---|---:|---|
| Public web news | Public articles from news websites | High for discovery | Licensing and reuse restrictions; source quality varies; difficult to reproduce if pages change |
| Licensed news feeds | Factiva, Bloomberg, LSEG, Dow Jones, other enterprise news/adverse media feeds | Very high | Cost and license constraints; usually better for enterprise auditability |
| Regulatory sources | SEC, DOJ, EPA, OSHA, EU Commission, FCA, national regulators, courts | Very high | Usually lower content risk because sources are official and public, but still needs structured ingestion |
| NGO and watchdog sources | Business & Human Rights Resource Centre, OECD Watch, environmental NGOs | Medium to high | Source bias and varying quality; useful but should be tagged as NGO/watchdog evidence |
| Company sources | Press releases, annual reports, sustainability reports, IR pages | Medium | Useful for company response, but not sufficient for controversy discovery |
| Social media | X/Twitter, Reddit, LinkedIn, forums | Low to medium | High noise; high privacy and terms-of-service risk; not recommended for MVP unless specifically approved |
| Portfolio data | Holdings, weights, internal ratings, analyst notes | Very high business value | Confidential; should not be sent to public web search or external grounding services without approval |
| Vendor ESG controversy data | MSCI, Sustainalytics, LSEG, RepRisk, etc. | High for benchmark/evaluation | Extra cost; licensing constraints; may not be available for MVP |

### 3.2 Minimum viable data for a low-risk MVP

For an MVP, I would avoid sensitive internal data and avoid broad uncontrolled web scraping. Use the smallest data scope that can prove the concept.

**Minimum sufficient MVP dataset:**

1. **Company universe:**
   - 30–50 public companies, not the full S&P 500 at first.
   - Use only public identifiers: company name, ticker, sector, major subsidiaries/brands.
   - Do not include actual portfolio weights, internal ratings, analyst notes, or client names.

2. **Source universe:**
   - Approved public regulatory and official sources.
   - A small list of credible public news domains if allowed by compliance.
   - Optional: Foundry Web Search for analyst-driven ad hoc testing, but not as the only production source.

3. **Stored data:**
   - Article title.
   - Source name.
   - URL.
   - Publication date.
   - Short snippet or summary.
   - ESG classification output.
   - Source citation.
   - Analyst review status.

4. **Avoid at MVP stage:**
   - Full internal portfolio holdings.
   - Client-specific exposures.
   - Non-public analyst notes.
   - Social media scraping.
   - Personal data extraction.
   - Full-text article storage if licensing is unclear.
   - Sending internal portfolio information into public web-search prompts.

### 3.3 Least-risk MVP design

The lowest-compliance-risk MVP would look like this:

```text
Public company list only
+ Approved public sources only
+ No confidential portfolio information
+ No client information
+ No social media
+ No full-text storage unless license permits
+ Store only metadata, URL, short snippet, model classification, and citation
+ Human review before any investment or ESG score use
```

This MVP can still prove the core value:

- Can the system find relevant negative ESG events?
- Can it avoid obvious false positives?
- Can it group duplicated articles into the same event?
- Can it classify events into E/S/G taxonomy?
- Can it produce a useful analyst memo with citations?

---

## 4. Compliance-Sensitive Data and Tool Choices

### 4.1 Web search and grounding

Foundry Web Search is useful for current public information and ad hoc analyst research. However, it should be used carefully in an enterprise investment environment.

Important design rule:

> Do not send confidential data such as portfolio weights, internal credit views, client names, internal watchlists, or unpublished analyst notes into a public web-grounding query unless legal/compliance has approved the data flow.

A safer prompt pattern is:

```text
Search recent public ESG controversies for Microsoft, Apple, and Tesla.
```

A riskier prompt pattern is:

```text
Search ESG controversies for our top 20 overweight portfolio positions, especially where our internal rating is high but our ESG analyst is concerned.
```

The second prompt leaks internal investment positioning and internal judgment into the search interaction.

### 4.2 Public web scraping

Public web scraping can create several problems:

- Website terms-of-service restrictions.
- Copyright and redistribution limits.
- Article paywall access issues.
- Robots.txt and scraping limitations.
- Changing URLs and page content, making audit difficult.
- Inconsistent article metadata.

For enterprise use, licensed news APIs are usually safer than ad hoc scraping.

### 4.3 Licensed news and adverse-media feeds

Licensed news/adverse-media feeds are often better for production because they usually provide:

- Clear commercial usage rights.
- Structured metadata.
- Better coverage.
- Historical archives.
- Entity tagging.
- Reproducibility.
- Support contracts.

The trade-off is cost. For MVP, it may be acceptable to start with public sources, but the design should leave room to plug in licensed feeds later.

### 4.4 Regulatory and official sources

For a low-risk MVP, official public sources are attractive:

- Regulators.
- Court releases.
- Enforcement actions.
- Sanctions lists.
- Government environmental or labor agencies.
- Official company disclosures.

These sources may miss early media controversies, but they provide high-quality evidence.

---

## 5. Core Data Processing Modules

### 5.1 Entity matching

Entity matching decides which company an article is really about.

It should handle:

- Parent companies.
- Subsidiaries.
- Brands.
- Executives.
- Suppliers and customers.
- Ambiguous names.
- False positives.

Example:

```text
"YouTube fined for child privacy violation"
→ Direct entity: YouTube
→ Parent company: Alphabet Inc.
→ Ticker: GOOGL
→ Relationship: Subsidiary
```

Example false positive:

```text
"Amazon rainforest deforestation worsens"
→ Not Amazon.com Inc.
```

### 5.2 Deduplication

Deduplication groups multiple articles about the same underlying event.

Example:

```text
Reuters: Apple fined by EU
Bloomberg: EU imposes penalty on Apple
FT: Apple loses EU App Store case
CNBC: Apple shares fall after EU fine
```

These should become one controversy event with four source articles, not four separate controversies.

### 5.3 ESG taxonomy classification

The classifier should map events into a controlled ESG taxonomy.

Example taxonomy:

| Pillar | Category |
|---|---|
| E | Pollution / environmental damage |
| E | Climate transition / greenwashing |
| E | Resource use / biodiversity |
| S | Labor rights / worker safety |
| S | Human rights / supply chain |
| S | Product safety / customer harm |
| S | Community impact |
| G | Corruption / bribery |
| G | Fraud / accounting / disclosure |
| G | Data privacy / cyber governance |
| G | Antitrust / business conduct |
| G | Board / executive misconduct |

### 5.4 Severity and confidence scoring

Severity should not be purely sentiment-based. It should reflect event type, evidence quality, scale, recurrence, regulatory involvement, and financial or reputational materiality.

Suggested fields:

```json
{
  "severity": 1,
  "confidence": 0.87,
  "novelty": "new_event",
  "source_quality": "regulator",
  "event_type": "regulatory_investigation",
  "financial_materiality": "medium",
  "reputational_materiality": "high",
  "analyst_review_status": "pending"
}
```

Severity scale:

| Score | Meaning |
|---:|---|
| 1 | Minor negative mention or weak allegation |
| 2 | Relevant controversy but limited evidence or small scale |
| 3 | Material controversy, credible source, possible business impact |
| 4 | Severe controversy, regulator/court involvement, repeated pattern, or clear operational impact |
| 5 | Major controversy with severe legal, financial, human, environmental, or franchise impact |

---

## 6. Suggested MVP Implementation Plan

### Phase 1 — Design the controlled data model

Create tables for:

- Company master.
- Alias/subsidiary table.
- Source whitelist.
- ESG taxonomy.
- Raw article metadata.
- Controversy event record.
- Article-to-event mapping.
- Analyst review outcomes.

### Phase 2 — Start with a narrow universe

Use 30–50 companies across several sectors:

- Technology.
- Energy.
- Banks.
- Healthcare.
- Consumer.

Do not start with the full S&P 500. You will not learn faster by creating 10 times more noisy alerts.

### Phase 3 — Use approved public sources

Begin with:

- Regulatory sources.
- Company disclosures.
- A small list of credible news sources if allowed.
- Optional Foundry Web Search for manual testing.

### Phase 4 — Build classification chain

For each candidate article:

1. Is this about the target company?
2. Is it negative or adverse?
3. Is it ESG-related?
4. Which ESG taxonomy category?
5. Is this new or duplicate/follow-up?
6. What is severity and confidence?
7. What evidence supports the classification?

### Phase 5 — Store in Azure AI Search

Index the event database for retrieval by:

- Company.
- Date.
- ESG pillar.
- Category.
- Severity.
- Source.
- Event type.
- Region.
- Sector.
- Text summary.
- Evidence snippets.

Use hybrid search because ESG questions often require both exact matching and semantic matching. For example, “worker safety” may match articles that use phrases such as “fatal accident,” “unsafe factory,” or “labor violations.”

### Phase 6 — Add the Foundry agent

The Foundry agent should be instructed to:

- Search the internal Azure AI Search controversy index first.
- Use public web search only when the user asks for latest/current information or when internal evidence is insufficient.
- Always cite sources.
- Separate confirmed events from unverified candidate events.
- Show confidence and uncertainty.
- Avoid making investment recommendations unless explicitly asked and supported by evidence.

---

## 7. Evaluation Strategy

Evaluation is difficult because the key failure mode is not only wrong answers. The bigger risk is **missed controversies**. A human reviewer can judge what the agent found, but may not know what the agent failed to find.

### 7.1 Evaluation dimensions

| Dimension | Question |
|---|---|
| Retrieval recall | Did the system find the relevant controversy articles/events? |
| Retrieval precision | Did it avoid irrelevant articles and false positives? |
| Entity accuracy | Did it link the event to the correct company, subsidiary, or supplier? |
| ESG classification accuracy | Did it assign the correct E/S/G pillar and category? |
| Severity accuracy | Is the severity score reasonable? |
| Deduplication accuracy | Did it group duplicate articles into one event? |
| Novelty detection | Did it correctly identify new events versus follow-ups? |
| Citation quality | Are the sources credible and do they support the claim? |
| Summary quality | Is the analyst memo accurate, concise, and useful? |
| Compliance behavior | Did the agent avoid exposing confidential data to external search tools? |

### 7.2 Human evaluation

Human evaluation is necessary but expensive.

Use a small sample:

- 20 companies.
- 4 weeks of history.
- Top 5–10 candidate events per company.
- Analyst labels each event as true positive, false positive, duplicate, wrong company, wrong ESG category, or wrong severity.

Pros:

- Best way to judge investment usefulness.
- Captures nuance that automatic metrics miss.
- Helps refine taxonomy and severity definitions.

Cons:

- Time-consuming.
- Analysts may not know what the system missed.
- Quality depends on reviewer expertise and consistency.

### 7.3 External benchmark evaluation

A second method is to compare against an external ESG controversy provider or adverse-media product.

Possible benchmark sources:

- MSCI ESG Controversies.
- Sustainalytics Controversies Research.
- LSEG / Refinitiv ESG controversy data.
- RepRisk.
- Dow Jones Risk & Compliance.

Pros:

- Gives a practical external baseline.
- Helps estimate missed events.
- Useful for senior stakeholder confidence.

Cons:

- Extra cost.
- Licensing restrictions.
- Vendor taxonomy may not match your internal taxonomy.
- Vendor data may itself contain delays or blind spots.

### 7.4 Practical low-cost evaluation for MVP

For the MVP, I would use a hybrid evaluation approach:

1. **Known-event test set**
   - Manually collect 50–100 known ESG controversy events from public sources.
   - Include different sectors and event types.
   - Test whether the system retrieves and classifies them correctly.

2. **Company-week sampling**
   - Pick 20 companies and 4 historical weeks.
   - Ask the system to generate controversy events for each company-week.
   - Human reviewer checks precision and severity.
   - Separately, reviewer performs quick manual search for missing events.

3. **Adversarial false-positive test set**
   - Include ambiguous company names and irrelevant ESG-like articles.
   - Examples: Amazon rainforest vs Amazon.com; Apple fruit vs Apple Inc.; Shell as a common noun vs Shell plc.
   - Measure whether the entity matcher rejects false positives.

4. **Duplicate clustering test**
   - Provide 5–10 articles about the same event.
   - Check whether the system creates one event cluster, not multiple events.

5. **Compliance red-team prompts**
   - Test whether the agent avoids sending confidential data into external web search.
   - Example: ask the agent to search using internal portfolio weights or analyst views and verify that it refuses or sanitizes the query.

### 7.5 Suggested MVP metrics

| Metric | MVP Target |
|---|---:|
| Article-level precision | >70% |
| Event-level precision | >75% |
| Known-event recall | >60% initially, then improve |
| Correct company/entity match | >85% |
| Correct ESG pillar | >80% |
| Correct broad severity band | >70% |
| Duplicate clustering accuracy | >75% |
| Citation support rate | >90% |
| Confidential-data leakage in test prompts | 0 tolerated |

These targets are intentionally realistic. Early systems often fail on recall and deduplication. Do not pretend the first version is investment-grade.

---

## 8. Recommended Agent Instructions

A useful initial instruction block:

```text
You are an ESG controversy monitoring agent for investment research.

Your task is to identify negative ESG-related controversy events involving public companies.

For each event, provide:
- Company name
- Matched entity: parent, subsidiary, supplier, product, executive, or other
- ESG pillar: E, S, or G
- Controversy category
- Event type
- Severity score from 1 to 5
- Confidence score
- Whether the event is new, duplicate, or follow-up
- Source name and publication date
- Citation / URL
- Short evidence-based summary
- Why it may matter for investors

Rules:
- Do not count multiple articles about the same underlying incident as multiple controversies.
- Do not classify neutral ESG disclosures as controversies unless there is a credible negative event, allegation, investigation, legal action, fine, accident, harm, or governance failure.
- If evidence is weak, label the event as low confidence.
- If the company match is uncertain, say so explicitly.
- Do not send confidential portfolio information, client names, internal ratings, or internal analyst notes into public web search.
- Prefer internal indexed evidence first. Use public web search only for current public information or when explicitly requested.
- Always cite sources.
```

---

## 9. Key Design Trade-Offs

| Design Choice | Lower-risk MVP | More powerful production system |
|---|---|---|
| Company universe | 30–50 public companies | Full portfolio / S&P 500 / global universe |
| Data source | Approved public sources | Licensed news + adverse media + regulatory + public web |
| Portfolio data | No internal exposure data | Internal holdings and materiality overlay |
| Web search | Manual/ad hoc | Controlled scheduled monitoring plus domain restrictions |
| Storage | Metadata and snippets | Full article archive if license permits |
| Evaluation | Human review + known events | Vendor benchmark + continuous labeled eval set |
| Output | Analyst memo | Alerts, dashboards, trend analytics, investment workflow integration |

---

## 10. My Recommended MVP

The best MVP is not “an agent that searches everything.” The best MVP is:

```text
30–50 public companies
+ approved public/regulatory/news sources
+ controlled ESG taxonomy
+ entity matching
+ event deduplication
+ Azure AI Search evidence index
+ Foundry agent for Q&A and summaries
+ human review workflow
```

Do not include confidential portfolio weights or internal ratings at the beginning. First prove that the agent can find, classify, deduplicate, and explain public controversy events with citations.

Once the MVP is reliable, add:

1. Licensed news/adverse-media feeds.
2. Larger company universe.
3. Portfolio exposure overlay.
4. Severity trend dashboard.
5. Alerts for high-severity new events.
6. Benchmark evaluation against external controversy vendors.

---

## 11. References and Useful Microsoft Documentation

- Microsoft Foundry Agent Service overview: https://learn.microsoft.com/en-us/azure/foundry/agents/overview
- Foundry Web Search Tool: https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/web-search
- Web grounding capabilities in Foundry: https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/web-overview
- Foundry tool catalog: https://learn.microsoft.com/en-us/azure/foundry/agents/concepts/tool-catalog
- Azure AI Search tool for Foundry agents: https://learn.microsoft.com/en-us/azure/foundry/agents/how-to/tools/ai-search
- Azure AI Search hybrid search overview: https://learn.microsoft.com/en-us/azure/search/hybrid-search-overview
- Azure AI Search semantic ranking overview: https://learn.microsoft.com/en-us/azure/search/semantic-search-overview
