---
type: reference
title: Ingestion
description: Defines the repeatable dlt flow from Wikipedia to PostgreSQL.
status: approved
modified: 2026-08-13T17:01:00+02:00
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

> Keep the extraction and load contract here. Parsing rules live in code, as
> docstrings on the module that owns them. Do not describe search indexing.

## Locked approach

Ingestion is a custom dlt source and resource. `dlt init` is never run, so
dependency ownership stays with `uv`, `pyproject.toml`, and `uv.lock`.

The pipeline reads wikitext from the Wikipedia Action API, returns cleaned
[corpus documents](corpus.md), and loads them straight into PostgreSQL. It does
not persist raw responses, use DuckDB, or require intermediate files.

## One run

```text
for season in 1..6:
    resolve the page and pin its revision ID
    yield the season introduction from the lead section
    parse the Episodes section into one entry per episode
    prefer a standalone article's Plot over the table summary
    yield one validated episode document each

dlt loads the yielded documents to PostgreSQL
validate counts, keys, required content, and season <= 6
```

Records are flat, so one resource produces one table and no child tables.

Fetching by revision ID makes a run repeatable even if a page changes mid-load.
Section indexes are discovered per revision, never hard-coded. The chosen page
titles and revision IDs form a small ingestion manifest: provenance, not a
raw-response archive or another storage layer.

Two request shapes cover the whole pipeline:

```text
action=parse&page={title}&prop=tocdata|revid&redirects=1
action=parse&oldid={revision_id}&section={section_id}&prop=wikitext|revid
```

The first resolves redirects, pins the revision, and lists the sections in one
answer, so the pipeline never asks for a revision separately.

Three modules own the detail, and their docstrings are the reference for it:
`wikipedia.py` for requests and section discovery, `wikitext.py` for parsing and
cleaning, and `documents.py` for assembling documents and validating a season.
[Corpus](corpus.md) owns which fields survive and why.

Parsing wikitext by hand is a deliberate choice, not the only option. Parser
libraries, preprocessor XML, Wikidata, and Parsoid HTML were each measured
against this corpus in
[Wikipedia extraction alternatives](research/wikipedia-extraction-alternatives.md).

dlt sends anonymous usage events to an external endpoint by default;
`.dlt/config.toml` turns that off. That file holds settings only, because
credentials are passed in code.

## Why not the dltHub AI Workbench

The workbench is dltHub's agent toolkit: a plugin marketplace of skills, a
`dlt-workspace-mcp` server, and the `dlt[hub]` package. It was read and rejected.

Its router maps "ingest from an HTTP API" to the `rest-api-pipeline` toolkit,
built on the declarative `rest_api` source and `dlt init` scaffolding. This
corpus is not a paginated REST resource; it is a handful of section fetches
returning wikitext that needs a custom parser, so the routed path is both the
wrong tool and the forbidden one. The workbench also expects a `dlthub`
workspace with its own CLI and project layout, duplicating what `uv` and
`pyproject.toml` already own.

Its credential rule is the sharpest conflict. The workbench forbids code that
reads credentials from a file and requires `dlt.secrets` backed by
`.dlt/secrets.toml`. That is the implicit resolution this project rejects: a
client picking credentials out of ambient config instead of being handed them.
The rule guards against an agent reading secrets into its context, which
permission rules in `.claude/settings.json` already prevent here. So `.env` plus
`dotenv_values` stays, and every client is passed its credentials explicitly. See
[Development](development.md).

Worth revisiting for the `data-exploration` toolkit during evaluation and
reporting work, which does not carry the ingestion scaffolding.

## API care

Requests carry a clear User-Agent and use low concurrency, timeouts, retries with
backoff, gzip, and Wikimedia's `maxlag` signal. A run fails rather than continues
when an expected season or episode cannot be validated.

## Refresh policy

The corpus is static for the project. Ingestion runs once during setup and again
only by an explicit refresh command. Rerunning replaces the table rather than
appending, so a refresh is safe to repeat. Nothing schedules it, because the
corpus is pinned to fixed revisions and does not drift; a timer would re-fetch
the same six pages to produce the same rows.

The [readme](../README.md) owns the exact commands, and `--help` on the module
lists the dry-run, per-season, and export options.

References: [MediaWiki parse API](https://www.mediawiki.org/wiki/API:Parsing_wikitext)
and [dlt PostgreSQL destination](https://dlthub.com/docs/dlt-ecosystem/destinations/postgres).
