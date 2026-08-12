---
type: reference
title: Evaluation
description: Defines the small offline and online checks used to choose the app defaults.
status: approved
modified: 2026-08-12T11:21:00+02:00
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

The set is committed as `evaluation/ground_truth.csv`, one row per question
carrying its `document_id`. Questions are fixed between runs, which is what makes
a score comparable to the one before it.

They were rewritten once, after the first round of measurements, and the phrasing
is what changed rather than the labels or the counts. The first set asked in
polished, uniform sentences that each named a character, town, or object; the
present one asks the way a viewer does, at varying length, and gives every
document at least one question carrying no proper noun at all. Documents,
per-document counts, and the held-out split are untouched, so the split still
covers what it did before. One question was found answerable by two documents
during the pass and relabelled.

Scores from before that rewrite do not compare to scores after it. The rewrite is
recorded here rather than smoothed over, because a benchmark that changes quietly
is worth less than one that changes in the open.

No model runs inside a retrieval measurement. Search, fusion, chunking, and
reranking are all deterministic given the same questions and the same index, so
a rerun reproduces a number rather than approximating it. This is part of why no
rewriting stage sits in front of search, as [Retrieval](retrieval.md) explains: a
model in that path would spread variance across every comparison, including the
ones it has nothing to do with. The agent rewrites its own queries, which is why
that variance lands in answer evaluation rather than here.

That holds for the pipeline and not for the deployed system, which is a boundary
worth naming. A measurement searches the question verbatim, once. The agent
searches verbatim first and then rewrites, as [Agent](agent.md) describes, so a
turn covers ground a single measured search does not. A retrieval score is
therefore what the paths reach on one well-put question, and neither a ceiling
nor a floor for what a whole turn retrieves. Answer evaluation runs the whole
loop and is what reads that.

The rewriting is what the gap was measured on: the agent's own phrasing reached
the answering document about six points less often than the question as asked,
which is why the first search now carries it unchanged.

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

Every question is anchored, because 126 episodes of one show are otherwise too
alike for any single document to be the answer: without an anchor, "which brother
is possessed by a demon" belongs to dozens of episodes and the label is simply
wrong. What the anchor may be is the part that changed. A named guest character,
town, or object is a rare term, which is what lexical ranking is best at, so a set
anchored that way leans towards it by construction. Every document therefore
carries at least one question anchored on a situation instead — the truck with
nobody driving it, the town where nobody can die — which identifies one episode
just as narrowly without handing lexical search a rare word.

The lean was real and is now measured rather than asserted. Rewriting the set
this way cost lexical 0.14 MRR and vector 0.05, so roughly a tenth of lexical's
apparent advantage was the anchoring rather than the retrieval. Nothing was
chosen to favour a path: the questions were written for how a viewer asks, and
the paths were re-measured afterwards. Vector search did not improve; it lost
less.

## Retrieval evaluation

The same questions run through lexical, vector, and hybrid RRF search, through
hybrid with cross-encoder reranking over it, and through the same with a deeper
cross-encoder, scored with hit rate at one and five and with MRR.
`uv run python -m supernatural_expert.evaluation` runs all five over the tuning
side and writes what each scored to `evaluation/results/retrieval_scores.csv` and
how each compares against the simpler setup it must beat to
`evaluation/results/retrieval_differences.csv`. That is lexical for the three
paths, the unreranked path for a reranked one, and the smaller cross-encoder for
the larger: every extra is judged against what it was added to.

`--held-out` scores the adopted setup alone over the questions no comparison saw,
writing `evaluation/results/retrieval_held_out.csv`.

Measuring and scoring are separate. A measurement is the rank the answering
document reached for each question, a document absent from the results counting
as no rank rather than a poor one. The metrics are arithmetic over those ranks,
so two setups can be compared question by question once the searching is done.

The metric that counts is whichever still separates good setups from bad ones.
The corpus holds 132 documents, so hit rate at five was expected to sit near a
perfect score and stop being useful. It does not: the best setup reaches 0.910,
leaving a question in eleven with its document nowhere in the results, so all
three measures remain live. MRR is the one a comparison is decided on, because
ordering is what a second stage can still move once recall is settled.

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
  the end, with the setup already chosen. Reading it with two setups to see which
  scores better would make it a second tuning set, and there would be nothing left
  to check the choice against. It answers "does the winner hold up", never "which
  should win", so the runner-up is never run against it.
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

`uv run python -m supernatural_expert.evaluation.answers` scores the adopted
setup and writes `evaluation/results/answer_scores.csv`. It is the only
measurement that runs the whole loop: retrieval scoring searches one question and
stops, while here the question is searched verbatim, the agent rewrites and
searches again if it needs to, and it is read on what it finally said.

`pydantic-evals` judges each answer twice, on whether it addresses the question
and on whether every claim appears in the documents cited with it. It fits the
Pydantic AI agent already in use and sends results to Logfire without a second
reporting path. A third measure costs nothing and needs no model: whether search
reached the labelled document at all, which is what separates a bad answer from
bad retrieval underneath it. Tokens per answer are recorded beside them, so the
cost of a setting is a number rather than an assumption.

Every verdict is written out with the judge's own justification, to
`answer_verdicts.csv`. The scores say how many answers failed; only the reasons
say what they got wrong, and reading a dozen of them is what turns a dropped
measure into a change worth making. That is how the instruction to answer at the
level of detail the documents hold was written, and it is the sampling by hand
that this section used to promise in the abstract.

Judging is the expensive part: each question costs one answer and two judge
calls. It therefore runs over 70 questions rather than the full set, stratified
by document kind and drawn from the tuning side. Two such samples are committed,
`evaluation/answer_subset_a.csv` and `answer_subset_b.csv`, sharing no question, so
a setup changed in response to one sample can be read again on the other.

How many documents an answer is written from was settled this way. Five and three
were compared question by question with the paired interval described above,
every measure tied, and the rule decided it: an interval containing zero is a tie,
and a tie goes to the simpler setup, which here is also the cheaper one. That
comparison ran on the answering model of the time, and nothing measured since has
given a reason to reopen it.

`--held-out` scores the adopted setup over the questions no tuning run has seen,
once, writing `answer_held_out.csv` beside its own verdicts. It answers "does the
winner hold up", never "which should win".

This is the one measurement that cannot be frozen. New answers need new verdicts,
so the judge runs live and two runs of the same setup will not agree exactly. The
judge model and its rubrics are pinned so that a change in the score is a change
in the system rather than in the ruler. The judge is deliberately not the
answering model, because a judge sharing the answerer's blind spots would pass
its own mistakes.

## Online evaluation

The Streamlit chat records thumbs-up and thumbs-down feedback. Live answer-judge
results and feedback go to Logfire and appear in reporting. Offline experiments
remain reproducible project artifacts; live signals show how the chosen setup
behaves after it is wired into the app.
