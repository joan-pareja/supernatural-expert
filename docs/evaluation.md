---
type: reference
title: Evaluation
description: Defines the small offline and online checks used to choose the app defaults.
status: approved
modified: 2026-08-08T23:29:00+02:00
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

The ground truth is synthetic questions generated from the corpus documents,
sized to how much text a document holds: about three per season table summary,
five per standalone plot, and four per season introduction. That is roughly 420
questions and covers every document, so none is missing from the benchmark.

Each question records the document that answers it. That label is what retrieval
is scored against.

The set is generated once and then committed, as `evaluation/ground_truth.csv`,
one row per question carrying its `document_id`. Questions never change between
runs, which is what makes a score comparable to the one before it.

No model runs inside a retrieval measurement. Search, fusion, chunking, and
reranking are all deterministic given the same questions and the same index, so
a rerun reproduces a number rather than approximating it. This is part of why
[Retrieval](retrieval.md) carries no query rewriting stage: a model in that path
would spread variance across every comparison, including the ones it has nothing
to do with.

Reviewing 420 questions by hand is not realistic in this project. The document
labels are checked across the whole set, which is quick and mechanical, while
answerability is read closely only on the smaller subset used for answer
evaluation.

## Keeping the questions fair

A question written from a document tends to reuse that document's exact words.
Full-text search then finds it easily, and lexical search looks better than it
would against how people really ask. The generator is asked to paraphrase and to
avoid copying distinctive wording, so lexical and vector search are compared on
even terms. Where the bias cannot be removed, the reported results say so.

One part of it cannot be removed. Every question is anchored on a named guest
character, town, or object, because 126 episodes of one show are otherwise too
alike for any single document to be the answer: without an anchor, "which brother
is possessed by a demon" belongs to dozens of episodes and the label is simply
wrong. Anchors are rare terms, which is what lexical ranking is best at, so the
set leans towards it by construction. That is a property of episodic retrieval
rather than a flaw to correct, and rewording questions until the paths draw level
would only make the measure less honest. The leaning is reported beside the
scores.

## Retrieval evaluation

The same questions run through lexical, vector, and hybrid RRF search, scored
with hit rate and MRR.

The metric that counts is whichever still separates good setups from bad ones.
The corpus holds 132 documents, so hit rate at five will sit near a perfect score
for every setup and stop being useful, while MRR, or hit rate at one, keeps
moving. This is confirmed against the first baseline before anything is tuned,
because a flat measure makes tuning pointless.

Retrieval scoring costs nothing but search time and arithmetic, so it runs over
the whole question set.

## Tuning

Optuna searches the parameters worth tuning: the RRF `k` constant, which sets how
strongly top ranks are favoured, the weight given to each search path, and how
many results each path contributes before fusion.

Chunking is tested as one comparison, split against unsplit, and nothing more.
Chunk sizes are not swept. The embedding model is not swept either; that choice
rests on public benchmarks, as [Retrieval](retrieval.md) explains.

## Not fooling ourselves

Every extra setup compared is another chance for one to fit these particular
questions by luck, so a winner picked from a wide search is partly a winner by
accident. Four defences, none of them a matter of care:

- The questions are split before any tuning starts, grouped by document, so
  questions about one episode never land on both sides.
- Tuning sees only the tuning side. The held-out side is read once, at the end.
- Both scores are reported. The gap between them is the measurement; a tuned
  number alone looks trustworthy whether or not it is.
- Overlapping confidence intervals, bootstrapped over the questions, count as a
  tie, and a tie goes to the simpler setup.

## Answer evaluation

At least two answer setups are compared, such as prompt or context choices.
`pydantic-evals` judges relevance and support from the retrieved text; it fits
the Pydantic AI agent already in use and sends results to Logfire without a
second reporting path.

Judging is the expensive part: every setup costs one answer and one judge call
per question. It therefore runs over a stratified subset of 60 to 80 questions
rather than the full set, with a sample inspected by hand.

This is the one measurement that cannot be frozen. A new answer setup produces
new answers, which need new verdicts, so the judge has to run live and two runs
of the same setup will not agree exactly. The judge model and its prompt are
pinned, verdicts are stored with the run, and a narrow margin between two answer
setups is read as a tie rather than a result.

## Online evaluation

The Streamlit chat records thumbs-up and thumbs-down feedback. Live answer-judge
results and feedback go to Logfire and appear in reporting. Offline experiments
remain reproducible project artifacts; live signals show how the chosen setup
behaves after it is wired into the app.
