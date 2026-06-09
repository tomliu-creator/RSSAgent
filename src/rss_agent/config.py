from __future__ import annotations

import csv
import os
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parents[2]


def load_env() -> None:
    load_dotenv(ROOT / ".env")
    load_dotenv(ROOT / ".env.local")


def load_yaml(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def load_companies(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def ensure_dirs() -> dict[str, Path]:
    paths = {
        "data": ROOT / "data",
        "raw_articles": ROOT / "data" / "raw" / "articles",
        "chunks": ROOT / "data" / "processed" / "chunks",
        "indexes": ROOT / "data" / "indexes",
        "runs": ROOT / "data" / "outputs" / "runs",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    return paths
