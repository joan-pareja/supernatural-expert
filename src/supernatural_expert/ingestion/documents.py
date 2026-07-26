"""Builds canonical corpus documents from Wikipedia pages.

This module owns the corpus rule: one row per searchable document, each with one
`content` field and flat provenance. Two kinds of document exist. An episode
document prefers a standalone article's Plot section and falls back to the season
table summary. A season introduction document carries the season page's lead,
which answers questions about a season as a whole that no episode can. See
docs/corpus.md.
"""

from collections import Counter
from dataclasses import asdict, dataclass
from datetime import date, datetime
from typing import Any, Literal

from supernatural_expert.ingestion.wikipedia import PageRevision, WikipediaClient
from supernatural_expert.ingestion.wikitext import (
    EpisodeListEntry,
    parse_episode_list,
    parse_prose_section,
)

SEASONS = range(1, 7)
SEASON_PAGE_TITLE = "Supernatural season {season}"
EPISODES_HEADING = "Episodes"
PLOT_HEADING = "Plot"

# Section 0 of any page is its lead, the prose before the first heading.
LEAD_SECTION_INDEX = "0"

# Broadcast history, not a moving target: these counts are what a correct run
# must produce, and a mismatch means the page changed shape or parsing broke.
EXPECTED_EPISODE_COUNTS = {1: 22, 2: 22, 3: 16, 4: 22, 5: 22, 6: 22}

DocumentType = Literal["episode", "season_introduction"]
ContentSource = Literal["standalone_plot", "season_table_summary", "season_lead"]


class CorpusError(RuntimeError):
    """Raised when the fetched corpus does not match what the project expects."""


@dataclass(frozen=True, slots=True)
class CorpusDocument:
    """One searchable document.

    Only `content` is chunked, embedded, and indexed. Every other field is either
    an identifier, a filter, a citation, or an answerable fact; nothing is kept
    that the application has no use for.

    Provenance is flat and describes where `content` came from. The season page
    that supplies episode metadata is always pinned by its own season
    introduction document, so no row needs a list of sources.
    """

    document_id: str
    document_type: DocumentType
    season_number: int
    episode_number: int | None
    title: str
    content: str
    content_source: ContentSource
    directed_by: str | None
    written_by: str | None
    original_air_date: date | None
    us_viewers_millions: float | None
    source_title: str
    source_url: str
    source_page_id: int
    source_revision_id: int
    retrieved_at: datetime

    def as_record(self) -> dict[str, Any]:
        """Return the plain dictionary dlt loads. It has no nested values."""
        return asdict(self)


def shared_article_titles(entries: list[EpisodeListEntry]) -> set[str]:
    """Return the standalone articles that more than one episode links to.

    An article covering several episodes, as the two parts of "All Hell Breaks
    Loose" do, is not about a single episode. Using it for each of them would
    store the same plot twice and make two search results compete, so those
    episodes keep their own distinct table summaries instead.
    """
    linked = Counter(
        entry.standalone_article_title
        for entry in entries
        if entry.standalone_article_title
    )
    return {title for title, count in linked.items() if count > 1}


def fetch_season_page(client: WikipediaClient, season: int) -> PageRevision:
    """Resolve one season page and pin its revision."""
    return client.resolve_page(SEASON_PAGE_TITLE.format(season=season))


def build_season_introduction(
    client: WikipediaClient, season: int, page: PageRevision, retrieved_at: datetime
) -> CorpusDocument:
    """Build the document that describes a season as a whole."""
    lead = parse_prose_section(
        client.fetch_section_wikitext(page.revision_id, LEAD_SECTION_INDEX),
        "Season lead",
    )
    return CorpusDocument(
        document_id=f"s{season:02d}",
        document_type="season_introduction",
        season_number=season,
        episode_number=None,
        title=page.title,
        content=lead,
        content_source="season_lead",
        directed_by=None,
        written_by=None,
        original_air_date=None,
        us_viewers_millions=None,
        source_title=page.title,
        source_url=page.url,
        source_page_id=page.page_id,
        source_revision_id=page.revision_id,
        retrieved_at=retrieved_at,
    )


def build_season_documents(
    client: WikipediaClient, season: int, retrieved_at: datetime
) -> list[CorpusDocument]:
    """Build the season introduction and every episode document for one season."""
    if season not in EXPECTED_EPISODE_COUNTS:
        raise CorpusError(
            f"Season {season} is outside the spoiler boundary of season 6."
        )

    season_page = fetch_season_page(client, season)
    documents = [build_season_introduction(client, season, season_page, retrieved_at)]

    entries = parse_episode_list(
        client.fetch_section_wikitext(
            season_page.revision_id, season_page.section_index(EPISODES_HEADING)
        )
    )
    shared = shared_article_titles(entries)

    for entry in entries:
        content = entry.season_table_summary
        content_source: ContentSource = "season_table_summary"
        source = season_page

        if (
            entry.standalone_article_title
            and entry.standalone_article_title not in shared
        ):
            article = client.resolve_page(entry.standalone_article_title)
            content = parse_prose_section(
                client.fetch_section_wikitext(
                    article.revision_id, article.section_index(PLOT_HEADING)
                ),
                "Plot",
            )
            content_source = "standalone_plot"
            source = article

        documents.append(
            CorpusDocument(
                document_id=f"s{season:02d}e{entry.season_episode_number:02d}",
                document_type="episode",
                season_number=season,
                episode_number=entry.season_episode_number,
                title=entry.title,
                content=content,
                content_source=content_source,
                directed_by=entry.directed_by,
                written_by=entry.written_by,
                original_air_date=entry.original_air_date,
                us_viewers_millions=entry.us_viewers_millions,
                source_title=source.title,
                source_url=source.url,
                source_page_id=source.page_id,
                source_revision_id=source.revision_id,
                retrieved_at=retrieved_at,
            )
        )

    validate_season(season, documents)
    return documents


def validate_season(season: int, documents: list[CorpusDocument]) -> None:
    """Fail the run when a season did not come back whole and usable."""
    introductions = [d for d in documents if d.document_type == "season_introduction"]
    if len(introductions) != 1:
        raise CorpusError(
            f"Season {season} produced {len(introductions)} introductions, expected 1."
        )

    episodes = [d for d in documents if d.document_type == "episode"]
    expected = EXPECTED_EPISODE_COUNTS[season]
    if len(episodes) != expected:
        raise CorpusError(
            f"Season {season} produced {len(episodes)} episodes, expected {expected}."
        )

    numbers = sorted(d.episode_number or 0 for d in episodes)
    if numbers != list(range(1, expected + 1)):
        raise CorpusError(
            f"Season {season} episode numbers are not 1..{expected}: {numbers}."
        )

    for document in documents:
        if document.season_number > max(SEASONS):
            raise CorpusError(
                f"{document.document_id} is past the spoiler boundary of season 6."
            )
        if not document.content.strip():
            raise CorpusError(f"{document.document_id} has no content.")
        if not document.title.strip():
            raise CorpusError(f"{document.document_id} has no title.")
        if document.source_revision_id <= 0 or document.source_page_id <= 0:
            raise CorpusError(
                f"{document.document_id} cites {document.source_title!r} "
                "without real identifiers."
            )
