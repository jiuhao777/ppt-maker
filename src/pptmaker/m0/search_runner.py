import json
import time
from pathlib import Path
from statistics import median
from typing import Protocol
from urllib.parse import urlsplit

from pptmaker.research.contracts import SearchResult


class SearchAdapter(Protocol):
    name: str

    def search(self, query: str, limit: int = 5) -> list[SearchResult]: ...


def run_queries(
    adapter: SearchAdapter,
    queries: list[str],
    output: Path,
    *,
    attempts: int = 3,
) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8") as handle:
        for query in queries:
            for attempt in range(attempts):
                started = time.perf_counter()
                try:
                    results = adapter.search(query, limit=5)
                    urls = [str(item.url) for item in results]
                    record = {
                        "provider": adapter.name,
                        "query": query,
                        "attempt": attempt,
                        "latency_seconds": time.perf_counter() - started,
                        "results": [item.model_dump(mode="json") for item in results],
                        "domains": sorted(
                            {urlsplit(url).hostname for url in urls if urlsplit(url).hostname}
                        ),
                        "duplicate_urls": len(urls) - len(set(urls)),
                        "error": None,
                    }
                except Exception as exc:
                    record = {
                        "provider": adapter.name,
                        "query": query,
                        "attempt": attempt,
                        "latency_seconds": time.perf_counter() - started,
                        "results": [],
                        "domains": [],
                        "duplicate_urls": 0,
                        "error": f"{type(exc).__name__}: {exc}",
                    }
                handle.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text("utf-8").splitlines() if line]


def summarize_records(records: list[dict]) -> dict[str, float | int]:
    latencies = sorted(float(item["latency_seconds"]) for item in records)
    successes = [item for item in records if item["error"] is None]
    return {
        "runs": len(records),
        "error_rate": 1 - len(successes) / max(len(records), 1),
        "p50_seconds": median(latencies) if latencies else 0.0,
        "domain_count": len({domain for item in successes for domain in item["domains"]}),
        "duplicate_urls": sum(int(item["duplicate_urls"]) for item in successes),
        "result_count": sum(len(item["results"]) for item in successes),
    }
