---
type: reference
title: Roadmap
description: Orders the two-week build.
status: approved
modified: 2026-08-09T22:37:00+02:00
tags:
- roadmap
- planning
related:
- ./docs/rubric.md
- ./ARCHITECTURE.md
---

# Roadmap

> Keep this as a short build order. Move settled design into its owning document.

## 1. Foundation

- Create the `uv` package, quality checks, Docker Compose, and PostgreSQL with
  pgvector and `pg_search`.
- Add a safe `.env.example` for `OPENAI_API_KEY` and Logfire credentials.

## 2. Corpus

- Build and test the dlt Wikipedia source for seasons 1 through 6.
- Load canonical corpus documents into PostgreSQL.
- Check episode counts, required fields, revision IDs, and spoiler limits.

## 3. Search and chat

- Add local ONNX embeddings and BM25 lexical search.
- Build all three retrieval paths: lexical, vector, and hybrid RRF. Choosing
  between them waits for the ground truth in step 4.
- Add the Pydantic AI agent, citations, abstention, and spoiler refusal.
- Build the Streamlit chat.

## 4. Quality and reporting

- Create and review a small synthetic ground-truth set.
- Compare the three retrieval paths and several answer setups against it, and
  adopt each winner on its measured result rather than for having been built.
- Add the cross-encoder reranking stage and measure it against hybrid alone.
- Send runs, judge results, and thumbs feedback to Logfire.
- Build at least five reporting charts from the Logfire Query API.

## 5. Delivery

- Test the clean Docker Compose flow on Windows.
- Add dashboard screenshots, example questions, results, and exact run commands.
- Pin dependency versions and prepare the public repository for peer review.
