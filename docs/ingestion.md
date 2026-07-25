---
type: reference
title: Ingestion
description: Defines the repeatable dlt flow from Wikipedia to PostgreSQL.
status: draft
modified: 2026-07-25T19:39:16+02:00
tags:
- ingestion
- dlt
- wikipedia
related:
- ./corpus.md
- ./data-model.md
- ../ARCHITECTURE.md
---

# Ingestion

> Keep the extraction and load contract here. Do not describe search indexing in
> this file.

## Locked approach

Use a custom dlt source and resource. Do not run `dlt init`; dependency ownership
stays with `uv`, `pyproject.toml`, and `uv.lock`.

The pipeline reads wikitext from the Wikipedia Action API, returns cleaned
[episode documents](corpus.md), and loads them straight into PostgreSQL. It does
not persist raw responses, use DuckDB, or require intermediate files.

## One run

```text
for season in 1..6:
    resolve the page and pin its current revision ID
    discover the Episodes section with action=parse, oldid, and prop=tocdata
    fetch that section with action=parse, oldid, and prop=wikitext
    parse each Episode list/sublist template

    for each episode:
        clean metadata and ShortSummary
        if Title points to a standalone article:
            discover and fetch its Plot section as wikitext
            replace content with the cleaned standalone plot
        attach page, revision, license, and retrieval provenance
        yield one validated episode document

dlt loads the yielded documents to PostgreSQL
validate counts, keys, required content, and season <= 6
```

Section numbers must be discovered; they are not stable page contracts.
`prop=sections` is deprecated, so use `prop=tocdata`. Fetching by revision ID
makes a run repeatable even if a page changes during the load. The chosen page
titles and revision IDs form a small ingestion manifest. It is provenance, not
a raw-response archive or another storage layer.

The important API request shapes are:

```text
action=query&titles={title}&prop=revisions&rvprop=ids|timestamp
action=parse&oldid={revision_id}&prop=tocdata|revid
action=parse&oldid={revision_id}&section={section_id}&prop=wikitext|revid
```

The season table parser reads the `Episode list/sublist` fields that are present,
such as episode numbers, title, credits, air date, production code, viewers, and
`ShortSummary`. dlt may normalize nested provenance into related tables; the
domain contract is still one episode document.

## API care

Use a clear User-Agent, low concurrency, timeouts, retries with backoff, gzip,
and Wikimedia's `maxlag` signal. Fail the run when an expected season or episode
cannot be validated.

## Refresh policy

The corpus is static for the project. Ingestion runs once during setup and again
only by an explicit refresh command. The course awards the automated dlt
pipeline; it does not require a scheduler.

References: [MediaWiki parse API](https://www.mediawiki.org/wiki/API:Parsing_wikitext)
and [dlt PostgreSQL destination](https://dlthub.com/docs/dlt-ecosystem/destinations/postgres).
