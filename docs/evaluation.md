---
type: reference
title: Evaluation
description: Defines the small offline and online checks used to choose the app defaults.
status: approved
modified: 2026-07-26T22:45:00+02:00
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

Generate synthetic questions from the corpus documents, sized to how much text a
document holds: about three per season table summary, five per standalone plot,
and four per season introduction. That is roughly 420 questions and covers every
document, so no document is missing from the benchmark.

Each question records the document that answers it. That label is what retrieval
is scored against.

Reviewing 420 questions by hand is not realistic in this project. Check the
document labels across the whole set, which is quick and mechanical, and review
answerability closely on the smaller subset used for answer evaluation.

## Keeping the questions fair

A question written from a document tends to reuse that document's exact words.
Full-text search then finds it easily, and lexical search looks better than it
would against how people really ask. Ask the generator to paraphrase and to avoid
copying distinctive wording, so lexical and vector search are compared on even
terms. Where the bias cannot be removed, say so when reporting results.

## Retrieval evaluation

Run the same questions through lexical, vector, and hybrid RRF search. Score with
hit rate and MRR.

Pick the metric that still separates good setups from bad ones. The corpus holds
132 documents, so hit rate at five will sit near a perfect score for every setup
and stop being useful. MRR, or hit rate at one, keeps moving. Confirm this
against the first baseline before tuning anything, because a flat measure makes
tuning pointless.

Retrieval scoring costs nothing but search time and arithmetic, so it runs over
the whole question set.

## Tuning

Use Optuna to search the parameters worth tuning: the RRF `k` constant, which
sets how strongly top ranks are favoured, the weight given to each search path,
and how many results each path contributes before fusion.

Tune on part of the question set and report the score on a held-out part. A
tuned number that only holds on the questions it was tuned against is worse than
an untuned one, because it looks trustworthy.

Add chunking and reranking as further experiments only once they can be measured
on this same set.

## Answer evaluation

Compare at least two answer setups, such as prompt or context choices. Judge
relevance and support from the retrieved text with `pydantic-evals`, which fits
the Pydantic AI agent already in use and sends results to Logfire without a
second reporting path.

Judging is the expensive part: every setup costs one answer and one judge call
per question. Run it over a stratified subset of 60 to 80 questions rather than
the full set, and inspect a sample by hand.

## Online evaluation

The Streamlit chat records thumbs-up and thumbs-down feedback. Live answer-judge
results and feedback go to Logfire and appear in reporting. Offline experiments
remain reproducible project artifacts; live signals show how the chosen setup
behaves after it is wired into the app.
