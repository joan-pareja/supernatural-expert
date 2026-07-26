---

type: reference
title: Corpus
description: Defines the Wikipedia corpus documents and the consolidation rule.
status: approved
modified: 2026-07-26T22:45:00+02:00
tags:

- corpus
- wikipedia
- supernatural
related:
- ../CONTEXT.md
- ./ingestion.md
- ./data-model.md

---

# Corpus

> Keep corpus scope, source meaning, and the final document shape here. Parsing
> steps belong in [Ingestion](ingestion.md).

## Source and boundary

The corpus uses the English Wikipedia Action API at
`https://en.wikipedia.org/w/api.php`. It covers *Supernatural* seasons 1 through
6: 126 episodes and 6 season introductions, so 132 documents. Data comes through
the API as wikitext; the pipeline does not scrape pages or save HTML files.

Wikipedia is the app's source of record. The agent should prefer retrieved
corpus text over its memory, cite it, and abstain when it is missing. This keeps
answers faithful without claiming that Wikipedia can never contain an error.

## Two kinds of document

**Episode documents** answer questions about a single episode. **Season
introduction documents** carry a season page's lead section, which describes the
season's arc, cast, network, and air dates. Those are facts no episode document
holds, and without them the app cannot answer a question about a season as a
whole.

Both kinds share one shape and one table, so retrieval reads a single set of
documents rather than combining several.

## Choosing an episode's text

Every season page has an episode table with a `ShortSummary`. Some episode titles
also link to a standalone article with a longer Plot section.

For each episode:

1. Parse the season table summary and metadata.
2. If the title links to a standalone episode article, fetch its Plot section.
3. Use the standalone plot as `content`; otherwise use the table summary.
4. Keep one document per episode, not two competing search results.

Season 1 shows both cases: `Pilot` links to `Pilot (Supernatural)`, while
`Wendigo` uses the season table summary. Twelve episodes take a standalone plot.

An article that covers more than one episode is not about a single episode. Both
parts of `All Hell Breaks Loose` link to one article, so using it for each would
store the same plot twice and make two search results compete. Episodes that
share an article keep their own table summaries instead.

## Document shape

```json
[
  {
    "document_id": "s01",
    "document_type": "season_introduction",
    "season_number": 1,
    "episode_number": null,
    "title": "Supernatural season 1",
    "content": "The first season of Supernatural, an American dark fantasy...",
    "content_source": "season_lead",
    "directed_by": null,
    "written_by": null,
    "original_air_date": null,
    "us_viewers_millions": null,
    "source_title": "Supernatural season 1",
    "source_url": "https://en.wikipedia.org/wiki/Supernatural_season_1",
    "source_page_id": 18569389,
    "source_revision_id": 0,
    "retrieved_at": "2026-07-26T10:00:00Z"
  },
  {
    "document_id": "s01e01",
    "document_type": "episode",
    "season_number": 1,
    "episode_number": 1,
    "title": "Pilot",
    "content": "In 1983, Lawrence, Kansas, Mary Winchester investigates...",
    "content_source": "standalone_plot",
    "directed_by": "David Nutter",
    "written_by": "Eric Kripke",
    "original_air_date": "2005-09-13",
    "us_viewers_millions": 5.69,
    "source_title": "Pilot (Supernatural)",
    "source_url": "https://en.wikipedia.org/wiki/Pilot_(Supernatural)",
    "source_page_id": 0,
    "source_revision_id": 0,
    "retrieved_at": "2026-07-26T10:00:00Z"
  }
]
```

Zero identifiers above mean "filled by the pipeline", not real Wikipedia values.

## Why these fields and no others

`content` is the only field that is chunked, embedded, and indexed. Every other
field earns its place by being an identifier, a retrieval filter, a citation, or
a fact a user can ask for:

- `document_id`, `document_type`, `season_number`, `episode_number`, `title`
identify a document, filter by season, and name it in an answer.
- `content_source` records which text won, so evaluation can compare how the
three kinds of text retrieve.
- `directed_by`, `written_by`, `original_air_date`, and `us_viewers_millions`
answer direct questions about an episode.
- `source_title`, `source_url`, `source_page_id`, and `source_revision_id` cite
the page the content came from and pin the revision that produced it.

Anything Wikipedia offers beyond this is not stored. Production codes and
series-wide episode numbers answer no question the app is for. The season table
summary is not kept beside a standalone plot, because the plot supersedes it and
a second text field invites double counting at index time. The CC BY-SA license
and the fact that markup was stripped hold for every row alike, so they belong
in [NOTICE](../NOTICE.md) rather than in 132 identical columns.

Provenance is flat, one source per row. An episode whose content comes from a
standalone article still relies on its season page for metadata, and that page is
pinned by the season's own introduction document, so the manifest stays complete
without a list of sources or a second table.

One JSON file per season may be exported for human inspection. PostgreSQL
documents remain the application source of truth.