---
type: reference
title: Course rubric
description: Maps the LLM Zoomcamp project rubric to planned evidence.
status: approved
modified: 2026-08-12T20:08:00+02:00
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
| Retrieval evaluation | 2 | Five setups scored over 343 questions, the winner adopted and confirmed once on held-out documents. See [Journey](../JOURNEY.md) and `evaluation/results/`. |
| LLM evaluation | 2 | Answers judged for relevance and support, four changes adopted on what it showed, and the result confirmed on 83 held-out questions. See [Evaluation](evaluation.md). |
| Interface | 2 | The Streamlit chat. A UI is the whole criterion; reporting is not part of it. |
| Ingestion pipeline | 2 | Automated dlt pipeline from the Wikipedia API. |
| Monitoring | 2 | Thumbs feedback in the chat, and a Logfire dashboard of six charts committed as `monitoring/dashboard.json`. See [Monitoring](monitoring.md). |
| Containerization | 2 | The chat and PostgreSQL both run through Docker Compose, and `docker compose up` is the whole of the setup. See [README](../README.md). |
| Reproducibility | 2 | Public data, pinned dependencies, and tested run steps. |

Base target: **18/18**.

## Best practices and bonus

| Item | Point | State |
|---|---:|---|
| Hybrid text and vector search | 1 | Built with RRF and measured against both paths alone. See [Retrieval](retrieval.md). |
| Document reranking | 1 | An `ms-marco-MiniLM-L-12-v2` cross-encoder over the hybrid candidates, measured against both plain hybrid and the smaller model, and adopted. See [Retrieval](retrieval.md). |
| User query rewriting | 1 | The agent composes its own search queries, measured against the question verbatim and constrained to searches after the first. See [Retrieval](retrieval.md). |
| Cloud deployment | 2 | Not pursued. |
| Exceptional work | up to 3 | A reviewer's to award, not a target to build towards. |

The technical target is **21 points without cloud**, and the locked plan
accounts for all of them.

Two points are declined rather than missed: cloud deployment is outside the
delivery target in [Scope](scope.md).

The official process also asks each student to review three peer projects. Each
review adds three points outside this implementation checklist.

## Evidence rule

A plan does not earn a point. Before submission, replace each planned statement
with a link to working code, an evaluation result, a screenshot, or exact run
instructions at the submitted commit. A reviewer does not need private Logfire
access when the public evidence makes the monitoring flow clear and reproducible
with their own project.
