---
type: reference
title: Data model
description: Names the small set of corpus and search records stored in PostgreSQL.
status: draft
modified: 2026-07-25T19:39:16+02:00
tags:
- data-model
- postgres
related:
- ./corpus.md
- ./retrieval.md
---

# Data model

> Keep this conceptual until dlt and the indexer prove the needed schema. Exact
> columns and SQL belong with the code.

PostgreSQL holds two ideas:

**Episode documents** are the canonical cleaned corpus. There is one per episode,
with metadata, one final content field, and Wikipedia provenance.

**Search units** are rebuildable pieces derived from episode documents. Each
keeps enough episode and source metadata for filtering and citations, plus its
text-search value and local embedding.

dlt owns normalization when it loads episode documents. The indexing code owns
search units. Changing chunking must rebuild search units without re-fetching or
duplicating the canonical corpus.

PostgreSQL native full-text search supplies lexical matching, and pgvector stores
embeddings. At this corpus size, exact vector search is the starting point; an
approximate index is not required.

Telemetry and feedback are not part of this model. They live only in Logfire, as
defined in [Monitoring](monitoring.md).
