---
type: reference
title: Retrieval
description: Defines the search baseline and evaluation-driven choices.
status: draft
modified: 2026-07-25T19:39:16+02:00
tags:
- retrieval
- hybrid-search
- rrf
related:
- ./data-model.md
- ./evaluation.md
- ../ROADMAP.md
---

# Retrieval

> Keep search behavior here. Record results in evaluation artifacts, not as
> claims in this plan.

## Search paths

- Lexical search uses PostgreSQL full-text search.
- Vector search uses local ONNX embeddings stored with pgvector.
- Hybrid search combines both ranked lists with reciprocal rank fusion (RRF).

All paths filter to seasons 1 through 6 and return source metadata for citations.
The Pydantic AI agent calls one typed search tool and answers only from its
results. If evidence is weak or missing, it says so instead of filling the gap
from model memory.

## Chunking

The first baseline uses one episode document as one search unit. Once a ground
truth exists, compare it with a simple paragraph-aware split for longer
standalone plots. Choose sizes, overlap, and metadata from measured results, not
guesswork.

Whether season introductions belong in the index remains open.

## Ranking terms

RRF is rank fusion: it combines lexical and vector result positions. It does not
score documents again against the query, so it does not satisfy the rubric's
separate document-reranking point. A true reranker remains an experiment in the
[Roadmap](../ROADMAP.md).
