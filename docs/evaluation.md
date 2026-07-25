---
type: reference
title: Evaluation
description: Defines the small offline and online checks used to choose the app defaults.
status: draft
modified: 2026-07-25T19:39:16+02:00
tags:
- evaluation
- quality
related:
- ./retrieval.md
- ./monitoring.md
- ./rubric.md
---

# Evaluation

> Keep the method here. Store questions, code, scores, and conclusions in the
> evaluation artifacts created during the build.

## Ground truth

Create a small synthetic question set from the episode documents, then manually
review it for answerability, episode labels, and spoilers. It is a practical
benchmark, not a claim of perfect truth.

## Retrieval evaluation

Run the same questions through lexical, vector, and hybrid RRF search. Later add
chunking or reranking experiments only when they can be compared on the same
set. Use the best measured setup in the application.

The exact metrics and cutoffs will be chosen with the first dataset. Do not set
thresholds before seeing its shape.

## Answer evaluation

Compare at least two answer setups, such as prompt or context choices, with the
same questions. Judge relevance and support from the retrieved text, inspect a
sample by hand, and use the best setup.

## Online evaluation

The Streamlit chat records thumbs-up and thumbs-down feedback. Live answer-judge
results and feedback go to Logfire and appear in reporting. Offline experiments
remain reproducible project artifacts; live signals show how the chosen setup
behaves after it is wired into the app.
