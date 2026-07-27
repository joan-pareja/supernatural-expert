---
type: reference
title: Course rubric
description: Maps the LLM Zoomcamp project rubric to planned evidence.
status: approved
modified: 2026-07-27T01:03:00+02:00
tags:
- rubric
- course
related:
- ../README.md
- ../ROADMAP.md
- ./evaluation.md
- ./monitoring.md
---

# Course rubric

> Keep this checklist aligned with the official rubric and update evidence as
> features land.

Source: [LLM Zoomcamp project documentation](https://github.com/DataTalksClub/llm-zoomcamp/blob/main/project.md).

## Base score

| Criterion | Target | Planned evidence |
|---|---:|---|
| Problem description | 2 | README and [Scope](scope.md) explain the user problem. |
| Retrieval flow | 2 | PostgreSQL knowledge base, Pydantic AI, and an LLM. |
| Retrieval evaluation | 2 | Compare several approaches and use the best. |
| LLM evaluation | 2 | Compare several answer setups and use the best. |
| Interface | 2 | Streamlit chat and reporting pages. |
| Ingestion pipeline | 2 | Automated dlt pipeline from the Wikipedia API. |
| Monitoring | 2 | Feedback, five chart queries, dashboard code, and screenshots. |
| Containerization | 2 | App and PostgreSQL run through Docker Compose. |
| Reproducibility | 2 | Public data, pinned dependencies, and tested run steps. |

Base target: **18/18**.

## Best practices and bonus

| Item | Point | State |
|---|---:|---|
| Hybrid text and vector search | 1 | Planned and evaluated with RRF. |
| Document reranking | 1 | Planned: an `ms-marco-MiniLM-L-6-v2` cross-encoder over the hybrid candidates. See [Retrieval](retrieval.md). |
| User query rewriting | 1 | Not pursued: a model call on every turn, and a non-deterministic step beside the evaluations. See [Retrieval](retrieval.md). |
| Cloud deployment | 2 | Not pursued. |

The technical target is **20 points without cloud**. The currently locked plan
accounts for **19**. Reranking is planned and scheduled for measurement but not
locked, because the evidence rule below counts a measured result and not an
intention.

Two points are declined rather than missed. Cloud deployment is outside the
delivery target in [Scope](scope.md), and query rewriting would cost more in
system complexity and reproducibility than one point returns.

The official process also asks each student to review three peer projects. Each
review adds three points outside this implementation checklist.

## Evidence rule

A plan does not earn a point. Before submission, replace each planned statement
with a link to working code, an evaluation result, a screenshot, or exact run
instructions at the submitted commit. A reviewer does not need private Logfire
access when the public evidence makes the monitoring flow clear and reproducible
with their own project.
