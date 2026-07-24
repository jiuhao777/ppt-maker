import re
from datetime import datetime
from html.parser import HTMLParser
from ipaddress import ip_address
from urllib.parse import urlsplit

from pptmaker.research.contracts import FactRecord, SearchResult
from pptmaker.security.network import is_forbidden_ip


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, _attrs):
        if tag in {"script", "style"}:
            self.hidden += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self.hidden:
            self.hidden -= 1

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


_INSTRUCTIONS = (
    re.compile(
        r"ignore (?:all |the )?previous instructions?[^。.!]*[。.!]?",
        re.I,
    ),
    re.compile(r"忽略(?:此前|之前|以上).*?(?:指令|提示)[^。.!]*[。.!]?"),
)


def _normalize_text(value: str) -> str:
    parser = _TextExtractor()
    parser.feed(value)
    text = " ".join(parser.parts)
    for pattern in _INSTRUCTIONS:
        text = pattern.sub("", text)
    return " ".join(text.split())[:2_000]


def _safe_result_url(value: str) -> bool:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return False
    try:
        return not is_forbidden_ip(str(ip_address(parsed.hostname)))
    except ValueError:
        return True


def normalize_results(
    project_id: str,
    results: list[SearchResult],
    accessed_at: datetime,
) -> list[FactRecord]:
    facts = []
    seen = set()
    for result in results:
        url = str(result.url)
        if not _safe_result_url(url):
            continue
        statement = _normalize_text(result.summary or result.snippet)
        key = (url, statement)
        if not statement or key in seen:
            continue
        seen.add(key)
        facts.append(
            FactRecord(
                project_id=project_id,
                statement=statement,
                source_url=result.url,
                source_title=result.title,
                site_name=result.site_name,
                published_at=result.published_at,
                accessed_at=accessed_at,
            )
        )
    return facts
