---
type: reference
title: Retrieval
description: Defines the search baseline and evaluation-driven choices.
status: approved
modified: 2026-07-27T02:09:00+02:00
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

## Embedding model

One encoder, `bge-small-en-v1.5`, picked from public benchmarks rather than from
this project's ground truth. A few hundred questions over 132 documents cannot
out-measure MTEB's fifteen retrieval datasets, and spending that small budget on
a component would weaken the path comparisons it exists to make.

It replaces the course's `all-MiniLM-L6-v2` because of what each was trained to
do. MiniLM learned whether two sentences mean the same thing; bge learned whether
a passage answers a question, which is the job here. Both are 384 dimensions and
run on CPU without a GPU or an embedding provider.

Embedding the whole corpus takes about twenty seconds. That is paid when the
index is built, never per query, but it is also paid once per experiment that
changes the index, which is part of why the comparisons in
[Evaluation](evaluation.md) stay few and deliberate.

## Chunking

Search units are built from `content` and from nothing else. Ingestion already
resolves each document to its single best text, so the indexer never has to
choose between two fields or risk indexing the same prose twice.

The baseline is one document, one search unit. Chunking is the challenger and is
expected to win, because an encoder reads a fixed number of tokens and silently
ignores the rest: unsplit, every standalone plot is represented by a fraction of
its text. [Evaluation](evaluation.md) settles it on measured results.

`semantic-text-splitter` does the splitting, in one dependency with none of its
own. It cuts at natural boundaries, paragraphs before sentences before words,
packs neighbours back together while there is room, and returns anything already
short enough untouched. Size is a ceiling rather than a target, and the ceiling
comes from the model's own window, so nothing here is fitted to this corpus.

Document length is uneven, and the comparison accounts for it. Standalone plots
run several times longer than season table summaries, while season introductions
sit near the summaries. A fixed-size split therefore gives the twelve plot-backed
episodes many more units than the rest, and more units means more chances to
match for reasons unrelated to relevance. Scores are aggregated per document so
that a split document competes as one result, and any chunking rule is judged
against the unsplit baseline on the same questions.

Ranking and answering therefore work at different sizes. A piece is what earns a
document its place in the results; the agent is then given that document's whole
`content`, never the piece alone. Small units sharpen the match without costing
the model the context around it.

## Ranking and reranking

RRF is rank fusion: it combines the positions a document took in the lexical and
vector lists. It never looks at the query again, which is why it is not
reranking and does not earn the rubric's separate point for it.

Reranking is a second stage over the first stage's output. Search casts a wide
net and returns its best twenty to fifty units, and a cross-encoder then reads
each one together with the query and scores it. The two models differ in where
the query enters. An embedding model compresses a document into 384 numbers
before any question exists, so that summary has to serve every question anyone
might ask. A cross-encoder takes the query and the passage as a single input, so
attention runs between them and the score reflects this pair rather than a guess
made in advance.

Accuracy costs time. Nothing can be precomputed, so the model runs once per
candidate at query time, which is affordable over twenty candidates and not over
a corpus. Recall is therefore the first stage's job and ordering the second's; a
document the first stage drops is gone for good. Ordering is also the part of
the score this corpus can still move, since hit rate saturates at 132 documents
while MRR keeps responding.

`ms-marco-MiniLM-L-6-v2` is the reranker, in ONNX on the same CPU as the encoder
and about the same size, 91 MB against 128 MB. It is trained on real search
queries paired with passages marked relevant or not, a narrower skill than the
sentence similarity an embedding model learns, and it returns a single relevance
score rather than a vector, so nothing about it reaches pgvector. Those scores
order candidates within one query and mean nothing across queries.

BAAI's own `bge-reranker-base` would match the encoder's family but is built on
multilingual XLM-RoBERTa and ships 1.1 GB of weights for languages this corpus
does not contain. English, CPU-sized, and ONNX-published are the properties that
matter here; a shared family name is not one of them.

Reranking is adopted only if it wins, as one comparison against the hybrid
baseline in [Evaluation](evaluation.md).

## Why there is no query rewriting

A rewriting stage would put a model between the user and search to resolve what
a follow-up refers to before anything is retrieved. It is a recognised technique
and the rubric offers a point for it. This project does without one.

It costs three things for that point. It adds a component and a frozen artifact
to maintain. It spends a model call on every turn, whether or not the question
needed one. And it places a non-deterministic step beside measurements whose
whole value is that a later run can be compared with an earlier one; the
rewriting would have to be frozen to keep them comparable, at which point the
evaluation no longer tests the rewriter that ships.

Follow-ups are not left broken. The agent already receives the conversation and
chooses the argument it passes to the search tool, so a question referring back
to an earlier turn is resolved inside a call that was happening regardless. That
is a property of the agent loop rather than a retrieval stage, which is why
nothing here measures it and nothing claims a point for it.
