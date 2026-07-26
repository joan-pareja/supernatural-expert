"""Tests for the pure wikitext parser.

These are worth writing because the parser is the one place where a silent
mistake produces plausible-looking but wrong corpus text. Fetching is not tested;
mocking the Action API would only assert that the mock was called.

The samples below are trimmed from the real season pages, keeping the constructs
that actually appear: nested templates inside field values, wiki links that carry
a pipe, citations, split writing credits, and em dashes.
"""

from datetime import date

import pytest

from supernatural_expert.ingestion.wikitext import (
    WikitextError,
    clean_text,
    iter_template_bodies,
    parse_credits,
    parse_episode_list,
    parse_prose_section,
    parse_start_date,
    parse_title_field,
    parse_viewers,
    template_fields,
)

LINKED_TITLE_ROW = """
{{Episode list/sublist|Supernatural season 1
| EpisodeNumber       = 1
| EpisodeNumber2      = 1
| Title               = [[Pilot (Supernatural)|Pilot]]
| DirectedBy          = [[David Nutter]]
| WrittenBy           = [[Eric Kripke]]
| OriginalAirDate     = {{Start date|2005|9|13}}
| ProdCode            = 475285
| Viewers             = 5.69<ref>{{#invoke:cite|web|url=https://example.org/a|title=Rankings|date=September 20, 2005}}</ref>
| ShortSummary        = Sam ([[Jared Padalecki]]) is forced back into the paranormal world by Dean.
| LineColor           = A9251E
}}
"""

PLAIN_TITLE_ROW = """
{{Episode list/sublist|Supernatural season 1
| EpisodeNumber       = 2
| EpisodeNumber2      = 2
| Title               = Wendigo
| DirectedBy          = David Nutter
| WrittenBy           = {{StoryTeleplay|s=Ron Milbauer & Terri Hughes Burton|t=Eric Kripke}}
| OriginalAirDate     = {{Start date|2005|9|20}}
| ProdCode            = 2T6901
| Viewers             = 5.01<ref name="week2" />
| ShortSummary        = The brothers head to [[Lost Creek Wilderness|Lost Creek, Colorado]] and kill a [[wendigo]].
| LineColor           = A9251E
}}
"""

SEASON_SECTION = f"""== Episodes ==
{{{{See also|List of Supernatural episodes}}}}
In this table, the number in the first column refers to the episode's number.
<onlyinclude>{{{{Episode table |background=#A9251E |overall=5 |season=5 |title=22 |dontclose=y
}}}}
{LINKED_TITLE_ROW}
{PLAIN_TITLE_ROW}
{{{{End}}}}</onlyinclude>
"""

PLOT_SECTION = """==Plot==
In 1983, [[Lawrence, Kansas]], [[Mary Winchester (Supernatural)|Mary Winchester]]
investigates a sound coming from her infant son Sam's nursery.

===Part one===
The brothers head to John's last known whereabouts&mdash;the town of Jericho&mdash;where
he had been investigating '''disappearances''' along a single stretch of road.
"""


class TestFieldSplitting:
    """The splitters must ignore separators that belong to nested markup."""

    def test_pipe_inside_a_wiki_link_does_not_split_a_field(self) -> None:
        fields = template_fields(
            iter_template_bodies(LINKED_TITLE_ROW, "Episode list/sublist")[0]
        )
        assert fields["Title"] == "[[Pilot (Supernatural)|Pilot]]"

    def test_pipes_inside_a_nested_template_do_not_split_a_field(self) -> None:
        fields = template_fields(
            iter_template_bodies(PLAIN_TITLE_ROW, "Episode list/sublist")[0]
        )
        assert fields["WrittenBy"] == (
            "{{StoryTeleplay|s=Ron Milbauer & Terri Hughes Burton|t=Eric Kripke}}"
        )

    def test_equals_inside_a_citation_does_not_become_a_field(self) -> None:
        fields = template_fields(
            iter_template_bodies(LINKED_TITLE_ROW, "Episode list/sublist")[0]
        )
        assert "url" not in fields
        assert "title" not in fields
        assert fields["Viewers"].startswith("5.69<ref>")

    def test_only_the_named_template_is_returned(self) -> None:
        # The section also holds See also, Episode table, and End templates.
        assert len(iter_template_bodies(SEASON_SECTION, "Episode list/sublist")) == 2


class TestCleanText:
    def test_labelled_link_keeps_its_label(self) -> None:
        assert (
            clean_text("go to [[Lost Creek Wilderness|Lost Creek]]")
            == "go to Lost Creek"
        )

    def test_bare_link_keeps_its_target(self) -> None:
        assert clean_text("a [[wendigo]] appears") == "a wendigo appears"

    def test_section_fragment_is_dropped_from_a_bare_link(self) -> None:
        assert (
            clean_text("[[List of characters#Jessica Moore]]") == "List of characters"
        )

    def test_citations_and_comments_are_removed(self) -> None:
        assert clean_text("5.69<ref>{{cite web|url=x}}</ref><!-- note -->") == "5.69"

    def test_self_closing_citation_is_removed(self) -> None:
        assert clean_text('5.01<ref name="week2" />') == "5.01"

    def test_entities_and_emphasis_are_resolved(self) -> None:
        assert clean_text("Jericho&mdash;where '''disappearances''' happened") == (
            "Jericho—where disappearances happened"
        )

    def test_remaining_templates_are_dropped(self) -> None:
        assert clean_text("text {{efn|a footnote}} more") == "text more"

    def test_paragraph_breaks_survive_but_runs_of_blank_lines_do_not(self) -> None:
        assert clean_text("one\n\n\n\ntwo") == "one\n\ntwo"


class TestTitleField:
    def test_disambiguated_link_separates_label_from_article(self) -> None:
        assert parse_title_field("[[Pilot (Supernatural)|Pilot]]") == (
            "Pilot",
            "Pilot (Supernatural)",
        )

    def test_bare_link_is_both_label_and_article(self) -> None:
        assert parse_title_field("[[Devil's Trap]]") == ("Devil's Trap", "Devil's Trap")

    def test_plain_title_has_no_standalone_article(self) -> None:
        assert parse_title_field("Wendigo") == ("Wendigo", None)


class TestScalarFields:
    def test_start_date_becomes_a_date(self) -> None:
        assert parse_start_date("{{Start date|2005|9|13}}") == date(2005, 9, 13)

    def test_missing_air_date_is_none(self) -> None:
        assert parse_start_date("") is None

    def test_split_writing_credit_is_expanded(self) -> None:
        assert parse_credits(
            "{{StoryTeleplay|s=Ron Milbauer & Terri Hughes Burton|t=Eric Kripke}}"
        ) == ("Story by Ron Milbauer & Terri Hughes Burton; Teleplay by Eric Kripke")

    def test_linked_credit_keeps_only_the_name(self) -> None:
        assert (
            parse_credits("[[Sera Gamble]] & [[Raelle Tucker]]")
            == "Sera Gamble & Raelle Tucker"
        )

    def test_viewers_drops_its_citation(self) -> None:
        assert parse_viewers("5.69<ref>{{#invoke:cite|web|url=x}}</ref>") == 5.69

    def test_missing_viewers_is_none(self) -> None:
        assert parse_viewers("TBA") is None


class TestParseEpisodeList:
    def test_entry_carries_the_cleaned_fields(self) -> None:
        first = parse_episode_list(SEASON_SECTION)[0]
        assert first.season_episode_number == 1
        assert first.series_episode_number == 1
        assert first.title == "Pilot"
        assert first.standalone_article_title == "Pilot (Supernatural)"
        assert first.directed_by == "David Nutter"
        assert first.original_air_date == date(2005, 9, 13)
        assert first.production_code == "475285"
        assert first.us_viewers_millions == 5.69
        assert first.season_table_summary.startswith(
            "Sam (Jared Padalecki) is forced back"
        )

    def test_row_without_an_episode_number_fails_the_run(self) -> None:
        with pytest.raises(WikitextError, match="EpisodeNumber2"):
            parse_episode_list("{{Episode list/sublist|Show\n| Title = Wendigo\n}}")

    def test_row_without_a_summary_fails_the_run(self) -> None:
        with pytest.raises(WikitextError, match="ShortSummary"):
            parse_episode_list(
                "{{Episode list/sublist|Show\n| EpisodeNumber2 = 3\n| Title = Skin\n}}"
            )


class TestParseProseSection:
    def test_headings_are_removed_but_their_prose_survives(self) -> None:
        plot = parse_prose_section(PLOT_SECTION, "Plot")
        assert "Plot" not in plot.splitlines()[0]
        assert "===" not in plot
        assert plot.startswith("In 1983, Lawrence, Kansas, Mary Winchester")
        assert plot.endswith("along a single stretch of road.")

    def test_a_lead_section_keeps_its_prose(self) -> None:
        # A season page lead opens with an infobox and carries no heading.
        lead = parse_prose_section(
            "{{Infobox television season\n| season_number = 1\n| num_episodes = 22\n}}\n"
            "The first season of ''[[Supernatural (American TV series)|Supernatural]]'' "
            "premiered on September 13, 2005.",
            "Season lead",
        )
        assert lead == (
            "The first season of Supernatural premiered on September 13, 2005."
        )

    def test_empty_section_fails_the_run(self) -> None:
        with pytest.raises(WikitextError, match="Plot section is empty"):
            parse_prose_section("==Plot==\n", "Plot")
