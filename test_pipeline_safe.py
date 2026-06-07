"""
Test pipeline: run rss_search then classify one item with adverse_bot logic.
Uses the same Azure AD auth as final_test_end_point_access.py.

Set these environment variables before running:
    AZURE_TENANT_ID
    AZURE_CLIENT_ID
    AZURE_CLIENT_SECRET
    AZURE_OPENAI_ENDPOINT
    AZURE_ASSISTANT_ID
"""

import os
import json
import time
import warnings
import ssl
import sys

# SSL fix for corporate network
for var in ['REQUESTS_CA_BUNDLE', 'CURL_CA_BUNDLE', 'SSL_CERT_FILE']:
    if var in os.environ:
        del os.environ[var]
ssl._create_default_https_context = ssl._create_unverified_context
warnings.filterwarnings('ignore')
try:
    import urllib3
    urllib3.disable_warnings()
except:
    pass

try:
    import feedparser
    from azure.identity import ClientSecretCredential
    from openai import AzureOpenAI, RateLimitError
except ImportError as e:
    print(f"Missing package: {e}. Run: pip install feedparser openai azure-identity", file=sys.stderr)
    sys.exit(1)

# ---- Azure AD config (set these as environment variables) ----
TENANT_ID      = os.environ.get("AZURE_TENANT_ID", "")
CLIENT_ID      = os.environ.get("AZURE_CLIENT_ID", "")
CLIENT_SECRET  = os.environ.get("AZURE_CLIENT_SECRET", "")
AZURE_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "")
ASSISTANT_ID   = os.environ.get("AZURE_ASSISTANT_ID", "")
API_VERSION    = "2025-04-01-preview"

missing = [k for k, v in {
    "AZURE_TENANT_ID": TENANT_ID,
    "AZURE_CLIENT_ID": CLIENT_ID,
    "AZURE_CLIENT_SECRET": CLIENT_SECRET,
    "AZURE_OPENAI_ENDPOINT": AZURE_ENDPOINT,
    "AZURE_ASSISTANT_ID": ASSISTANT_ID,
}.items() if not v]
if missing:
    print(f"Missing environment variables: {', '.join(missing)}", file=sys.stderr)
    sys.exit(1)

# ---- Step 1: fetch one RSS feed ----
QUERY = "KKR Reputation Risk"
CEID = "US:en"
lang, region = CEID.split(":")[1], CEID.split(":")[0]
q = QUERY.replace(" ", "+")
rss_url = f"https://news.google.com/rss/search?q={q}&hl={lang}&gl={region}&ceid={CEID}"

print(f"\n[1/3] Fetching RSS: {rss_url}")
feed = feedparser.parse(rss_url)
items = feed.entries[:3]  # limit to 3 for the test
print(f"      Found {len(feed.entries)} items, using first {len(items)}")

if not items:
    print("No RSS items found. Check query or network.")
    sys.exit(0)

# ---- Step 2: connect to Azure OpenAI ----
print("\n[2/3] Connecting to Azure OpenAI...")
credential = ClientSecretCredential(
    tenant_id=TENANT_ID,
    client_id=CLIENT_ID,
    client_secret=CLIENT_SECRET
)
client = AzureOpenAI(
    azure_endpoint=AZURE_ENDPOINT,
    api_version=API_VERSION,
    azure_ad_token_provider=lambda: credential.get_token("https://cognitiveservices.azure.com/.default").token
)
print("      Connected.")

user_instructions = (
    'Classify this news item as Adverse Media or not. '
    'Return ONLY a JSON object with the following fields: '
    '{"classification": "Adverse or Not Adverse", '
    '"publisher": "Publisher of the newsitem", '
    '"translation": "english translation of the news item", '
    '"explanation": "short English explanation why", '
    '"summary": "the summary in plain text", '
    '"risk": "risk score for APG AM low/med/high"}'
)

def call_assistant(payload):
    thread = client.beta.threads.create()
    client.beta.threads.messages.create(
        thread_id=thread.id,
        role="user",
        content=user_instructions + "\n\n" + payload
    )
    run = client.beta.threads.runs.create(
        thread_id=thread.id,
        assistant_id=ASSISTANT_ID
    )
    while run.status in ['queued', 'in_progress', 'cancelling']:
        time.sleep(1)
        run = client.beta.threads.runs.retrieve(thread_id=thread.id, run_id=run.id)
    if run.status != 'completed':
        return f"Run failed with status: {run.status}"
    messages = client.beta.threads.messages.list(thread_id=thread.id)
    return messages.data[0].content[0].text.value.strip()

# ---- Step 3: classify items ----
print(f"\n[3/3] Classifying {len(items)} items...\n")
results = []
for i, entry in enumerate(items):
    title = entry.get("title", "")
    summary = entry.get("summary", "")
    link = entry.get("link", "")
    published = entry.get("published", "")

    print(f"  Item {i+1}: {title[:80]}")
    payload = f"Title: {title}\nSummary: {summary}\nLink: {link}"

    raw = call_assistant(payload)
    try:
        result = json.loads(raw)
    except Exception:
        result = {"classification": raw, "explanation": "Model did not return JSON."}

    result["title"] = title
    result["link"] = link
    result["published"] = published
    results.append(result)
    print(f"           -> {result.get('classification', '?')} | risk: {result.get('risk', '?')}")

# ---- Save output ----
out_path = "test_pipeline_results.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"\nDone. Results saved to {out_path}")
