---
type: reference
title: Retrieval
description: Defines the search baseline and evaluation-driven choices.
status: approved
modified: 2026-08-09T22:19:00+02:00
tags:
- retrieval
- hybrid-search
- rrf
related:
- ./agent.md
- ./data-model.md
- ./evaluation.md
- ../ROADMAP.md
---

# Retrieval

> Keep search behavior here. Record results in evaluation artifacts, not as
> claims in this plan.

## Search paths

- Lexical search uses BM25, through the `pg_search` extension.
- Vector search uses local ONNX embeddings stored with pgvector.
- Hybrid search combines both ranked lists with reciprocal rank fusion (RRF).

Hybrid ships, though it only ties lexical on the ground truth. Those questions
each name a rare guest character, town, or object, because
[Evaluation](evaluation.md) has to anchor them for a label to mean anything, and
rarity is exactly what BM25 ranks best. Questions asked in use are not all that
shape: one about how a season ends, or what a recurring idea amounts to, offers no
rare term to seize on, and that is where the vector path is expected to carry the
result. Keeping hybrid is a forecast rather than a measured win, taken knowingly
against the tie rule that would otherwise keep the simpler path, and it stands
until questions from real use say otherwise.

All paths filter to seasons 1 through 6 and return source metadata for citations.
The agent reaches them through one typed search tool; [Agent](agent.md) owns what
it may then claim.

The spoiler boundary is the corpus itself, not a search argument. Nothing past
season 6 was ever loaded, so no filter has to hold the line and none is offered.
A `through_season` argument would be chosen by the model on each call, which
makes it a preference rather than a guarantee: whatever can set it correctly can
set it to 6. What remains is the agent recognising an empty result as an empty
result, which is the same discipline every other unanswerable question needs.

## Embedding model

One encoder, `bge-small-en-v1.5`, picked from public benchmarks rather than from
this project's ground truth. A few hundred questions over 132 documents cannot
out-measure MTEB's fifteen retrieval datasets, and spending that small budget on
a component would weaken the path comparisons it exists to make.

It replaces the course's `all-MiniLM-L6-v2` because of what each was trained to
do. MiniLM learned whether two sentences mean the same thing; bge learned whether
a passage answers a question, which is the job here. Both are 384 dimensions and
run on CPU without a GPU or an embedding provider.

The same family's larger size is defined beside it and is not the default. It
scores higher, but a paired bootstrap over the ground truth puts zero inside
every confidence interval, and an improvement this corpus cannot demonstrate does
not earn three times the weights and three times the indexing time.

Embedding the whole corpus takes under half a minute on a laptop CPU, and scales
with whatever machine runs it. That is paid when the index is built, never per
query, but it is also paid once per experiment that changes the index, which is
part of why the comparisons in [Evaluation](evaluation.md) stay few and
deliberate. The weights are a separate one-time cost of 128 MB, downloaded rather
than committed.

## Chunking

Search units are built from `content` and from nothing else. Ingestion already
resolves each document to its single best text, so the indexer never has to
choose between two fields or risk indexing the same prose twice.

Documents are chunked to the encoder's window. An encoder reads a fixed number of
tokens and silently ignores the rest, so a whole standalone plot would be
represented by a fraction of its own text while a season table summary fits
entire. Chunking is what puts the two on even terms, and is a property of the
model rather than a setting to search.

`semantic-text-splitter` does the splitting, in one dependency with none of its
own. It cuts at natural boundaries, paragraphs before sentences before words,
packs neighbours back together while there is room, and returns anything already
short enough untouched. Size is a ceiling rather than a target, and the ceiling
comes from the model's own window, so nothing here is fitted to this corpus.

Document length is uneven, and aggregation accounts for it. Standalone plots
run several times longer than season table summaries, while season introductions
sit near the summaries. A fixed-size split therefore gives the twelve plot-backed
episodes many more units than the rest, and more units means more chances to
match for reasons unrelated to relevance. Scores are aggregated per document so
that a split document competes as one result.

Ranking and answering therefore work at different sizes. A piece is what earns a
document its place in the results; the agent is then given that document's whole
`content`, never the piece alone. Small units sharpen the match without costing
the model the context around it.

Pieces are embedded exactly as they are cut, with no episode header prepended.
Prefixing the season, episode number, and title would put an episode's name inside
every vector, and matching a name is not what an encoder is for: an anchor earns
its place by being rare, and rarity is what BM25 measures and what a dense vector
flattens. The lexical path already covers it, from the title as its own indexed
field, so a header buys the vector path little and costs the rule that embedded
text is the stored text.

## Ranking and reranking

Lexical ranking is BM25, over the title and the piece as two indexed fields. A
question matches disjunctively: a unit carrying any of its terms is a candidate,
and the score reflects how many it carries and how rare each one is across the
corpus. That rarity term is the whole point. In a question naming both Dean and
the Roadhouse, `dean` appears in almost every unit and separates nothing, while
`roadhous` appears in a handful and identifies the episode outright.

No field weight is assigned by hand. BM25 normalises for field length, so a term
found in a short title already counts for more than the same term buried in a
plot, which is the effect a weight would have been chosen to produce. Leaving it
alone also removes a dial that a ground truth of a few hundred questions is
easily tuned into.

BM25 replaced PostgreSQL's own `tsvector` ranking, which was built first and
found barely to work. `plainto_tsquery` joins a question's stems with AND, so a
unit missing any one of them does not match at all, and `ts_rank` reads only
within a document, leaving a term that occurs in nearly every unit worth as much
as one that occurs in five. It retrieved 8 of 426 ground truth questions where
BM25 retrieves 400. The measurements are kept with the evaluation artifacts.

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

Reranking is adopted on one comparison against the hybrid baseline, and it wins
it: MRR moves from 0.808 to 0.881 and hit rate at one from 0.738 to 0.840, with
the paired interval clear of zero. It is the largest effect measured on this
corpus and the only extra that is not close. Every answer therefore goes through
it, switched on where the agent's tool calls search rather than chosen by the
model, for the reason the spoiler boundary is not an argument either.

It costs about 1.6 seconds a query, against 0.2 for hybrid alone, which is
affordable beside the model call that follows it. The shortlist is twenty units,
and halving it is the lever if that ever stops being true.

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
