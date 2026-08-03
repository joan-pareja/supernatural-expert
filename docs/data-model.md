---
type: reference
title: Data model
description: Names the small set of corpus and search records stored in PostgreSQL.
status: approved
modified: 2026-08-04T01:19:00+02:00
tags:
- data-model
- postgres
related:
- ./corpus.md
- ./retrieval.md
---

# Data model

> Keep this at the level of what is stored and why. Exact columns, types, and SQL
> belong with the code.

PostgreSQL holds two ideas:

**Corpus documents** are the canonical cleaned corpus, one row per searchable
document in a single flat table. Episodes and season introductions share that
table, so retrieval reads one set of documents instead of combining several.
Records have no nested values, so the loader produces no child tables. Fields
that vary per document are stored; anything constant across the corpus is
documented rather than repeated on every row. See [Corpus](corpus.md).

**Search units** are rebuildable pieces derived from corpus documents. Each keeps
enough document and source metadata for filtering and citations, plus its
text-search value and local embedding.

Search units are built from `content` alone. It is the one field that ingestion
resolves to a single best text per document, which is what keeps one episode from
producing two competing results.

Both search paths read the same units. Lexical matching has no length limit and
would not need them, but RRF fuses positions in two ranked lists, and positions
only mean the same thing when both lists rank the same things.

dlt owns normalization when it loads corpus documents. The indexing code owns
search units. Changing chunking must rebuild search units without re-fetching or
duplicating the canonical corpus.

The two owners hold separate schemas, `corpus` and `search`. dlt may drop and
recreate the dataset it owns on a refresh, which would take a co-located table
with it, so nothing derived is stored where dlt can reach it. For the same reason
a search unit copies the document fields it needs rather than referencing them: a
foreign key could not survive that refresh, and the copies let every search read
a single table. A rebuild replaces the whole table in one transaction, since
derived data has no state worth migrating.

PostgreSQL native full-text search supplies lexical matching, and pgvector stores
embeddings.

Vector search is exact, over a sequential scan, with no HNSW or IVFFlat index.
Approximate indexes trade recall for speed and earn that trade in the tens of
thousands of vectors. This corpus holds a few hundred, so an exact scan is both
faster, having no index to traverse or build, and perfectly recalling. Adding one
here would cost accuracy and gain nothing measurable. Revisit if the corpus ever
grows by two orders of magnitude, which the fixed season 1 to 6 boundary rules
out.

Telemetry and feedback are not part of this model. They live only in Logfire, as
defined in [Monitoring](monitoring.md).
