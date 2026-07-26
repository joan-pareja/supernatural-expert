---
type: reference
title: Retrieval
description: Defines the search baseline and evaluation-driven choices.
status: approved
modified: 2026-07-26T22:45:00+02:00
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

Search units are built from `content` and from nothing else. Ingestion already
resolves each document to its single best text, so the indexer never has to
choose between two fields or risk indexing the same prose twice.

The baseline uses one corpus document as one search unit. A paragraph-aware split
for longer standalone plots is the alternative, and the ground truth in
[Evaluation](evaluation.md) decides between them. Sizes, overlap, and metadata
come from measured results.

Document length is uneven, and the comparison accounts for it. Standalone plots
run several times longer than season table summaries, while season introductions
sit near the summaries. A fixed-size split therefore gives the twelve plot-backed
episodes many more units than the rest, and more units means more chances to
match for reasons unrelated to relevance. Scores are aggregated per document so
that a split document competes as one result, and any chunking rule is judged
against the unsplit baseline on the same questions.

## Ranking terms

RRF is rank fusion: it combines lexical and vector result positions. It does not
score documents again against the query, so it does not satisfy the rubric's
separate document-reranking point. A true reranker is a separate experiment,
tracked in the [Roadmap](../ROADMAP.md) and measured like any other setup.
