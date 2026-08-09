---
type: reference
title: Evaluation
description: Defines the small offline and online checks used to choose the app defaults.
status: approved
modified: 2026-08-09T22:37:00+02:00
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
five per standalone plot, and four per season introduction. That is 426 questions
over all 132 documents, so none is missing from the benchmark.

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

Reviewing 426 questions by hand is not realistic in this project. The document
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

The same questions run through lexical, vector, and hybrid RRF search, and
through hybrid with cross-encoder reranking over it, scored with hit rate at one
and five and with MRR. `uv run python -m supernatural_expert.evaluation` runs all
four over the tuning side and writes what each scored to
`evaluation/results/retrieval_scores.csv` and how each compares against the
simpler setup it must beat to `evaluation/results/retrieval_differences.csv`.
That is lexical for the three paths, and the unreranked path for a reranked one:
every extra is judged against what it was added to.

Measuring and scoring are separate. A measurement is the rank the answering
document reached for each question, a document absent from the results counting
as no rank rather than a poor one. The metrics are arithmetic over those ranks,
so two setups can be compared question by question once the searching is done.

The metric that counts is whichever still separates good setups from bad ones.
The corpus holds 132 documents, so hit rate at five was expected to sit near a
perfect score and stop being useful. It does not: the best setup reaches 0.936,
leaving a sixteenth of the questions with their document nowhere in the results,
so all three measures remain live. MRR is the one a comparison is decided on,
because ordering is what a second stage can still move once recall is settled.

Retrieval scoring costs nothing but search time and arithmetic, so it runs over
every question on the side being read.

## Tuning

Optuna was to search what fusion exposes: the RRF `k` constant, a weight for each
search path, and the depth each path contributes before fusion. Separating the
measurement from the scoring was partly for its benefit, so a trial could
re-score ranks it already held rather than search again.

It was dropped once the paths were measured, because each of those parameters
turned out to be settled without it. `k` is the published default of 60, and it
flattens the top positions by design; moving it shifts fused ranks too little to
repay the run. A candidate depth of 50 already reaches far past where either path
still contributes over 132 documents. A per-path weight is the one dial that
would have moved the result, and it is also exactly the dial a few hundred
questions fit rather than measure: a lead bought that way is one the held-out
side would not confirm. Chunk size and the embedding model follow the encoder
rather than these questions, as [Retrieval](retrieval.md) explains.

The ground truth is spent on comparing whole setups instead. That is what settled
hybrid against its two parts and reranking against hybrid, and the reranker moved
the score by more than any search over fusion could have.

## Not fooling ourselves

Every extra setup compared is another chance for one to fit these particular
questions by luck, so a winner picked from a wide search is partly a winner by
accident. Four defences, none of them a matter of care:

- The questions are split before any setup is compared, grouped by document, so
  questions about one episode never land on both sides. The split is a list of
  documents rather than of questions, `evaluation/held_out.csv`, which is what
  makes that structural: a fifth of the documents are held out, sampled from each
  document kind separately so the six season introductions cannot all land on one
  side. It is generated once from a fixed seed and committed, and a test
  regenerates it to confirm the committed file is the one the seed produces.
- Every comparison sees only the tuning side. The held-out side is read once, at
  the end.
- Both scores are reported. The gap between them is the measurement; the chosen
  setup's own number looks trustworthy whether or not it is.
- A setup is compared against a simpler one question by question, and the
  difference between the two is what carries the confidence interval. Every setup
  answers the same questions, so each question yields a pair, and subtracting
  removes the difficulty the two share instead of measuring it twice. Two
  separate intervals can overlap while the difference between the setups is real,
  which is why an overlap is not read as a tie. An interval on that difference
  which still contains zero counts as a tie, and a tie goes to the simpler setup.
  The search path departs from that once, on grounds [Retrieval](retrieval.md)
  states.

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
