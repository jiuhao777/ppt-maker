import re
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Protocol

from pptmaker.m2.interview import RequirementExtraction
from pptmaker.research.bocha import SearchError
from pptmaker.research.contracts import (
    ResearchRun,
    SearchQuery,
    SearchResult,
    WebPolicy,
)
from pptmaker.research.facts import normalize_results
from pptmaker.research.freshness import resolve_freshness
from pptmaker.research.repository import ResearchRepository


class SearchKeyRequired(ValueError):
    pass


class SearchProvider(Protocol):
    def search(
        self, query: SearchQuery, api_key: str
    ) -> list[SearchResult]: ...


_SENSITIVE = re.compile(
    r"(?i)(?:api[_-]?key|authorization|bearer|sk-[a-z0-9_-]+|"
    r"[\w.+-]+@[\w.-]+\.[a-z]{2,})"
)


class FreshnessService:
    def __init__(
        self,
        search: SearchProvider,
        repository: ResearchRepository,
        *,
        clock: Callable[[], datetime] | None = None,
    ):
        self.search = search
        self.repository = repository
        self.clock = clock or (lambda: datetime.now(timezone.utc))

    def _save(self, run: ResearchRun) -> ResearchRun:
        self.repository.save_run(run)
        return run

    def plan(
        self,
        project_id: str,
        policy: WebPolicy,
        extraction: RequirementExtraction,
    ) -> ResearchRun:
        purpose = str(extraction.brief.purpose.value or "")
        decision = resolve_freshness(
            policy,
            purpose,
            extraction.ai_freshness,
        )
        return self._save(
            ResearchRun(
                project_id=project_id,
                policy=policy,
                decision=decision,
                status="PLANNED" if decision.requires_web else "NOT_REQUIRED",
            )
        )

    def run(
        self,
        project_id: str,
        policy: WebPolicy,
        extraction: RequirementExtraction,
        bocha_key: str,
        *,
        freshness: str = "oneYear",
    ) -> ResearchRun:
        purpose = str(extraction.brief.purpose.value or "")
        decision = resolve_freshness(
            policy,
            purpose,
            extraction.ai_freshness,
        )
        if not decision.requires_web:
            return self._save(
                ResearchRun(
                    project_id=project_id,
                    policy=policy,
                    decision=decision,
                    status="NOT_REQUIRED",
                )
            )
        if not bocha_key:
            if policy == "ALWAYS":
                raise SearchKeyRequired("强制联网需要配置搜索 API Key")
            return self._save(
                ResearchRun(
                    project_id=project_id,
                    policy=policy,
                    decision=decision,
                    status="SKIPPED_NO_KEY",
                )
            )

        candidates = [purpose, *decision.safe_queries]
        queries = []
        for value in candidates:
            value = " ".join(value.split())[:500]
            if value and not _SENSITIVE.search(value) and value not in queries:
                queries.append(value)
            if len(queries) == 5:
                break
        results = []
        try:
            for value in queries:
                results.extend(
                    self.search.search(SearchQuery(query=value, freshness=freshness), bocha_key)
                )
        except SearchError as exc:
            return self._save(
                ResearchRun(
                    project_id=project_id,
                    policy=policy,
                    decision=decision,
                    status="FAILED",
                    safe_error_type=type(exc).__name__,
                )
            )
        facts = normalize_results(project_id, results, self.clock())
        self.repository.replace_facts(project_id, facts)
        return self._save(
            ResearchRun(
                project_id=project_id,
                policy=policy,
                decision=decision,
                status="COMPLETED",
                fact_ids=[item.id for item in facts],
            )
        )
