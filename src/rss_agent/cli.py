from __future__ import annotations

import argparse
from datetime import datetime

from .classifier import AssistantClassifier
from .config import ROOT, ensure_dirs, load_companies, load_env, load_yaml
from .downloader import download_article
from .events import build_events, render_report
from .io_utils import write_json, write_jsonl, write_text
from .ranking import rank_candidates
from .rss import collect_rss_candidates
from .vector_store import LocalVectorStore


def run_pipeline(args: argparse.Namespace) -> None:
    load_env()
    paths = ensure_dirs()
    run_id = datetime.now().strftime("%Y%m%d_%H%M%S")

    companies = load_companies(ROOT / "config" / "company_universe.csv")
    if args.company_id:
        companies = [c for c in companies if c["company_id"].lower() == args.company_id.lower()]
    policy = load_yaml(ROOT / "config" / "source_policy.yaml")

    print(f"[1/7] Collecting RSS candidates for {len(companies)} company record(s)")
    candidates = collect_rss_candidates(
        companies=companies,
        ceid=policy.get("rss", {}).get("ceid", "US:en"),
        max_items_per_query=int(policy.get("rss", {}).get("max_items_per_query", 10)),
        base_query=args.query,
    )
    write_jsonl(paths["runs"] / f"{run_id}_candidates.jsonl", [c.to_dict() for c in candidates])
    print(f"      Collected {len(candidates)} candidates")

    print("[2/7] Ranking candidates")
    top = rank_candidates(candidates, policy, max_articles=args.max_items)
    write_jsonl(paths["runs"] / f"{run_id}_top_candidates.jsonl", [c.to_dict() for c in top])
    print(f"      Selected {len(top)} top candidates")

    print("[3/7] Downloading top candidate articles")
    articles = [
        download_article(
            candidate,
            paths["raw_articles"],
            store_full_text=bool(policy.get("download", {}).get("store_full_text", True)),
        )
        for candidate in top
    ]
    write_jsonl(paths["runs"] / f"{run_id}_articles.jsonl", [a.to_dict() for a in articles])
    print(f"      Downloaded/extracted {sum(1 for a in articles if a.extracted_text)} article(s)")

    print("[4/7] Indexing article evidence locally")
    vector_store = LocalVectorStore(paths["indexes"] / "chroma", reset=args.reset_index)
    chunk_count = vector_store.add_articles(articles, paths["chunks"] / f"{run_id}_chunks.jsonl")
    print(f"      Indexed {chunk_count} chunks")

    print("[5/7] Classifying ESG controversy candidates")
    classifier = AssistantClassifier()
    classifications = [classifier.classify(article) for article in articles]
    write_jsonl(paths["runs"] / f"{run_id}_classifications.jsonl", [c.to_dict() for c in classifications])
    print(f"      Classified {len(classifications)} candidate(s)")

    print("[6/7] Building event records")
    events = build_events(classifications)
    write_json(paths["runs"] / f"{run_id}_events.json", events)
    print(f"      Built {len(events)} candidate event(s)")

    print("[7/7] Writing analyst report")
    report = render_report(events, classifications)
    report_path = paths["runs"] / f"{run_id}_analyst_report.md"
    write_text(report_path, report)
    print(f"      Report: {report_path}")


def query_index(args: argparse.Namespace) -> None:
    load_env()
    paths = ensure_dirs()
    vector_store = LocalVectorStore(paths["indexes"] / "chroma")
    results = vector_store.query(args.text, top_k=args.top_k)
    for i, result in enumerate(results, start=1):
        meta = result["metadata"]
        print(f"\n[{i}] distance={result['distance']:.4f}")
        print(f"Title: {meta.get('title')}")
        print(f"Company: {meta.get('company_name')} | Publisher: {meta.get('publisher')}")
        print(f"URL: {meta.get('canonical_url')}")
        print(result["text"][: args.preview_chars])


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the ESG controversy RSS agent MVP.")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="Collect, download, index, classify, and report.")
    run.add_argument("--query", default=None, help="Optional single RSS query to use for all selected companies.")
    run.add_argument("--company-id", default="APG", help="Company ID from config/company_universe.csv.")
    run.add_argument("--max-items", type=int, default=3, help="Number of top candidates to download/classify.")
    run.add_argument("--reset-index", action="store_true", help="Clear the local Chroma collection before indexing this run.")
    run.set_defaults(func=run_pipeline)

    ask = sub.add_parser("ask", help="Query the local vector evidence store.")
    ask.add_argument("text", help="Evidence search query.")
    ask.add_argument("--top-k", type=int, default=5)
    ask.add_argument("--preview-chars", type=int, default=700)
    ask.set_defaults(func=query_index)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
