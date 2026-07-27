import re
from collections.abc import Callable
from datetime import datetime, timezone

from pptmaker.m2.models import DeckOutline
from pptmaker.m2.outlines import build_research_tasks
from pptmaker.research.bocha import SearchError
from pptmaker.research.contracts import (
    FreshnessDecision,
    ResearchRun,
    SearchQuery,
    SearchResult,
    WebPolicy,
)
from pptmaker.research.facts import normalize_results
from pptmaker.research.repository import ResearchRepository
from pptmaker.research.service import SearchKeyRequired, SearchProvider


_SENSITIVE = re.compile(
    r"(?i)(?:api[_-]?key|authorization|bearer|sk-[a-z0-9_-]+|"
    r"[\w.+-]+@[\w.-]+\.[a-z]{2,})"
)


class PostOutlineResearch:
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

    def run(
        self,
        project_id: str,
        outline: DeckOutline,
        policy: WebPolicy,
        decision: FreshnessDecision,
        bocha_key: str,
        *,
        freshness: str = "oneYear",
    ) -> ResearchRun:
        if outline.project_id != project_id or outline.status != "APPROVED":
            raise ValueError("research requires the approved project outline")
        if policy == "NEVER" or not decision.requires_web:
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
                raise SearchKeyRequired("search API key is required")
            return self._save(
                ResearchRun(
                    project_id=project_id,
                    policy=policy,
                    decision=decision,
                    status="SKIPPED_NO_KEY",
                )
            )

        candidates = [
            task.search_hint or task.question
            for task in build_research_tasks(outline)
        ]
        if not candidates:
            candidates = [outline.narrative]
        queries = []
        for value in candidates:
            normalized = " ".join(value.split())[:500]
            if (
                normalized
                and normalized not in queries
                and not _SENSITIVE.search(normalized)
            ):
                queries.append(normalized)
            if len(queries) == 5:
                break
        results: list[SearchResult] = []
        try:
            for value in queries:
                results.extend(
                    self.search.search(
                        SearchQuery(query=value, freshness=freshness),
                        bocha_key,
                    )
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
