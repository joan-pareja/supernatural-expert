"""A small typed client for the English Wikipedia Action API.

Only the three request shapes the corpus needs are exposed. Everything the
client returns is pinned to a revision ID, so a run reads exactly the same text
even if an editor changes a page while it is running.
"""

import urllib.parse
from dataclasses import dataclass
from typing import Any

from dlt.sources.helpers.requests import Client

API_URL = "https://en.wikipedia.org/w/api.php"
ARTICLE_URL = "https://en.wikipedia.org/wiki/"


class WikipediaError(RuntimeError):
    """Raised when the API refuses a request or returns an unusable page."""


@dataclass(frozen=True, slots=True)
class PageRevision:
    """A page pinned to one revision, which is also the provenance we store.

    `section_indexes` maps a casefolded heading to the section index the API
    wants. It is captured with the revision because indexes shift whenever an
    editor adds or removes a section, so an index is only meaningful next to the
    revision it came from.
    """

    title: str
    page_id: int
    revision_id: int
    url: str
    section_indexes: dict[str, str]

    def section_index(self, heading: str) -> str:
        """Return the index of the section with this heading."""
        index = self.section_indexes.get(heading.strip().casefold())
        if index is None:
            raise WikipediaError(
                f"Revision {self.revision_id} of {self.title!r} has no {heading!r} "
                f"section. Sections: {sorted(self.section_indexes)}."
            )
        return index


class WikipediaClient:
    """Reads wikitext from the Action API, one request at a time.

    Requests stay sequential on purpose. The corpus is six season pages plus a
    handful of episode articles, so concurrency would only add load to a donated
    service for no useful gain.
    """

    def __init__(
        self,
        user_agent: str,
        *,
        api_url: str = API_URL,
        request_timeout: float = 30.0,
        max_attempts: int = 5,
        maxlag: int = 5,
    ) -> None:
        if not user_agent.strip():
            raise WikipediaError(
                "Wikimedia requires a descriptive User-Agent; set WIKIPEDIA_USER_AGENT in .env."
            )
        self._api_url = api_url
        self._maxlag = maxlag
        # Wikimedia answers an overloaded-replica request with 503 and a
        # Retry-After header, so honouring that header is what implements maxlag.
        self._client = Client(
            request_timeout=request_timeout,
            request_max_attempts=max_attempts,
            request_backoff_factor=2,
            respect_retry_after_header=True,
            raise_for_status=True,
        )
        self._client.session.headers.update(
            {"User-Agent": user_agent, "Accept-Encoding": "gzip"}
        )

    def _call(self, **params: str | int) -> dict[str, Any]:
        query: dict[str, str | int] = {
            "format": "json",
            "formatversion": 2,
            "maxlag": self._maxlag,
            **params,
        }
        # dlt's Client.get overloads are only partially resolvable by Pyright.
        response = self._client.get(  # pyright: ignore[reportUnknownMemberType]
            self._api_url, params=query
        )
        payload: dict[str, Any] = response.json()
        if "error" in payload:
            raise WikipediaError(f"Action API error for {params!r}: {payload['error']}")
        return payload

    def resolve_page(self, title: str) -> PageRevision:
        """Follow redirects, pin the current revision, and index the sections.

        One request does all three. `action=parse` returns the resolved title,
        page ID, and revision ID alongside the table of contents, so a separate
        revision lookup would only repeat what this already answers.
        `prop=sections` is deprecated; `prop=tocdata` replaces it. A missing page
        comes back as an API error, which `_call` raises.
        """
        payload = self._call(
            action="parse", page=title, prop="tocdata|revid", redirects=1
        )
        parsed: dict[str, Any] = payload["parse"]
        sections: list[dict[str, Any]] = parsed["tocdata"]["sections"]

        # First match wins, matching the API's own section numbering when a page
        # repeats a heading.
        indexes: dict[str, str] = {}
        for section in sections:
            indexes.setdefault(
                str(section["line"]).strip().casefold(), str(section["index"])
            )

        resolved: str = parsed["title"]
        return PageRevision(
            title=resolved,
            page_id=int(parsed["pageid"]),
            revision_id=int(parsed["revid"]),
            url=ARTICLE_URL + urllib.parse.quote(resolved.replace(" ", "_")),
            section_indexes=indexes,
        )

    def fetch_section_wikitext(self, revision_id: int, section_index: str) -> str:
        """Fetch one section's raw wikitext from a pinned revision."""
        payload = self._call(
            action="parse",
            oldid=revision_id,
            section=section_index,
            prop="wikitext|revid",
        )
        wikitext: str = payload["parse"]["wikitext"]
        if not wikitext.strip():
            raise WikipediaError(
                f"Section {section_index} of revision {revision_id} is empty."
            )
        return wikitext
