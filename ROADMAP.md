---
type: reference
title: Roadmap
description: Orders the two-week build and records decisions that are still open.
status: approved
modified: 2026-07-26T22:45:00+02:00
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
  pgvector.
- Add a safe `.env.example` for `OPENAI_API_KEY` and Logfire credentials.

## 2. Corpus

- Build and test the dlt Wikipedia source for seasons 1 through 6.
- Load canonical corpus documents into PostgreSQL.
- Check episode counts, required fields, revision IDs, and spoiler limits.

## 3. Search and chat

- Add local ONNX embeddings and PostgreSQL text search.
- Build all three retrieval paths: lexical, vector, and hybrid RRF. Choosing
  between them waits for the ground truth in step 4.
- Add the Pydantic AI agent, citations, abstention, and spoiler refusal.
- Build the Streamlit chat.

## 4. Quality and reporting

- Create and review a small synthetic ground-truth set.
- Compare the three retrieval paths and several answer setups against it, then
  tune and adopt the winners.
- Send runs, judge results, and thumbs feedback to Logfire.
- Build at least five reporting charts from the Logfire Query API.

## 5. Delivery

- Test the clean Docker Compose flow on Windows.
- Add dashboard screenshots, example questions, results, and exact run commands.
- Pin dependency versions and prepare the public repository for peer review.

## Open decisions

- Choose and benchmark the exact ONNX embedding model and vector size.
- Test chunking after the baseline evaluation exists.
- Select a true document reranker. RRF combines ranks; it is not reranking.
- Decide whether query rewriting earns its best-practice point.
