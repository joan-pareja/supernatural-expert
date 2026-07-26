"""Tests for the corpus rule that decides which text becomes an episode's content.

Fetching and assembly are not tested; a stubbed Action API would only prove the
stub was called. The one decision worth pinning is which standalone articles are
rejected, because getting it wrong silently duplicates content across documents.
"""

import pytest

from supernatural_expert.ingestion.documents import shared_article_titles
from supernatural_expert.ingestion.wikipedia import PageRevision, WikipediaError
from supernatural_expert.ingestion.wikitext import EpisodeListEntry


def entry(episode: int, title: str, article: str | None) -> EpisodeListEntry:
    return EpisodeListEntry(
        series_episode_number=episode,
        season_episode_number=episode,
        title=title,
        standalone_article_title=article,
        directed_by="",
        written_by="",
        original_air_date=None,
        production_code="",
        us_viewers_millions=None,
        season_table_summary="A summary.",
    )


class TestSharedArticleTitles:
    def test_an_article_used_by_two_episodes_is_shared(self) -> None:
        entries = [
            entry(
                21,
                "All Hell Breaks Loose (Part 1)",
                "All Hell Breaks Loose (Supernatural)",
            ),
            entry(
                22,
                "All Hell Breaks Loose (Part 2)",
                "All Hell Breaks Loose (Supernatural)",
            ),
        ]
        assert shared_article_titles(entries) == {
            "All Hell Breaks Loose (Supernatural)"
        }

    def test_an_article_used_once_is_not_shared(self) -> None:
        entries = [
            entry(1, "Pilot", "Pilot (Supernatural)"),
            entry(2, "Wendigo", None),
            entry(22, "Devil's Trap", "Devil's Trap"),
        ]
        assert shared_article_titles(entries) == set()

    def test_episodes_without_an_article_are_ignored(self) -> None:
        entries = [entry(2, "Wendigo", None), entry(3, "Dead in the Water", None)]
        assert shared_article_titles(entries) == set()


class TestSectionIndex:
    """Section lookup is pure once a page is resolved, so it is tested directly."""

    def page(self) -> PageRevision:
        return PageRevision(
            title="No Rest for the Wicked (Supernatural)",
            page_id=28290773,
            revision_id=1356072184,
            url="https://en.wikipedia.org/wiki/No_Rest_for_the_Wicked_(Supernatural)",
            # Plot sits at index 2 here and at index 1 on most other articles,
            # which is why indexes are read per revision rather than hard-coded.
            section_indexes={"production": "1", "plot": "2", "reception": "3"},
        )

    def test_heading_lookup_ignores_case_and_spacing(self) -> None:
        assert self.page().section_index("  Plot  ") == "2"

    def test_missing_heading_names_what_was_available(self) -> None:
        with pytest.raises(WikipediaError, match="has no 'Episodes' section"):
            self.page().section_index("Episodes")
