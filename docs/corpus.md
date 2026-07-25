---
type: reference
title: Corpus
description: Defines the Wikipedia episode corpus and consolidation rule.
status: draft
modified: 2026-07-25T19:39:16+02:00
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

> Keep corpus scope, source meaning, and the final episode shape here. Parsing
> steps belong in [Ingestion](ingestion.md).

## Source and boundary

The corpus uses the English Wikipedia Action API at
`https://en.wikipedia.org/w/api.php`. It covers *Supernatural* seasons 1 through
6: about 126 episodes. Data comes through the API as wikitext; the pipeline does
not scrape pages or save HTML files.

Wikipedia is the app's source of record. The agent should prefer retrieved
corpus text over its memory, cite it, and abstain when it is missing. This keeps
answers faithful without claiming that Wikipedia can never contain an error.

## Two forms of episode text

Every season page has an episode table with a `ShortSummary`. Some episode titles
also link to a standalone article with a longer Plot section.

For each episode:

1. Parse the season table summary and metadata.
2. If the title links to a standalone episode article, fetch its Plot section.
3. Use the standalone plot as `content`; otherwise use the table summary.
4. Keep one episode document, not two competing search results.

Season 1 shows both cases: `Pilot` links to `Pilot (Supernatural)`, while
`Wendigo` uses the season table summary.

## Clean episode shape

This is an illustrative shape, not a locked database schema:

```json
[
  {
    "episode_id": "s01e01",
    "season_number": 1,
    "episode_number": 1,
    "title": "Pilot",
    "standalone_article_title": "Pilot (Supernatural)",
    "content_source": "standalone_plot",
    "content": "Clean text from the standalone Plot section...",
    "source_pages": [
      {
        "title": "Supernatural season 1",
        "page_id": 0,
        "revision_id": 0,
        "url": "https://en.wikipedia.org/wiki/Supernatural_season_1"
      },
      {
        "title": "Pilot (Supernatural)",
        "page_id": 0,
        "revision_id": 0,
        "url": "https://en.wikipedia.org/wiki/Pilot_(Supernatural)"
      }
    ]
  },
  {
    "episode_id": "s01e02",
    "season_number": 1,
    "episode_number": 2,
    "title": "Wendigo",
    "standalone_article_title": null,
    "content_source": "season_table_summary",
    "content": "Clean text from the season table summary...",
    "source_pages": [
      {
        "title": "Supernatural season 1",
        "page_id": 0,
        "revision_id": 0,
        "url": "https://en.wikipedia.org/wiki/Supernatural_season_1"
      }
    ]
  }
]
```

Real records also keep available episode metadata, retrieval time, the CC BY-SA
license marker, and a modified-text marker. The zero IDs above mean “filled by
the pipeline,” not real Wikipedia values.

One JSON file per season may be exported for human inspection. PostgreSQL episode
documents remain the application source of truth.
