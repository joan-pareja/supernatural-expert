---
type: reference
title: Retrieval
description: Defines the search baseline and evaluation-driven choices.
status: approved
modified: 2026-08-13T17:01:00+02:00
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

Hybrid ships, and it is measured rather than forecast. It beats lexical by 0.070
MRR with the paired interval clear of zero, while vector alone loses to lexical
by 0.050: the two paths find different documents, and fusing them beats either.

It was not always so clear. On the first question set, every question named a
rare guest character, town, or object, because [Evaluation](evaluation.md) has to
anchor them for a label to mean anything, and rarity is exactly what BM25 ranks
best. Hybrid tied lexical there and shipped anyway, as a forecast about questions
asked in use. Rewriting those questions to the way viewers actually ask, with at
least one per document naming nothing at all, cost lexical 0.14 MRR and vector
0.05 and turned the tie into a decided win. The forecast was right, and the
earlier lean was the anchoring rather than the ranking.

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

Document length is uneven, and aggregation accounts for it. The twelve episodes
carrying a standalone plot average about 3,300 characters, the 114 summarised in
a season table about 950, and the six season introductions about 1,400. Every one
of them is a compact, informative document; the spread is a matter of how much
Wikipedia records about an episode, not of some being unwieldy.

That spread is still enough to matter once documents are split. The twelve plots
yield 48 of the 180 search units while the 114 summaries yield 123, so a plot has
several pieces competing where a summary has one, and more pieces means more
chances to match for reasons unrelated to relevance. Scores are therefore
aggregated per document, so a split document competes as one result.

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
vector lists, and never looks at the query again.

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

`ms-marco-MiniLM-L-12-v2` is the reranker, in ONNX on the same CPU as the
encoder. It is trained on real search queries paired with passages marked
relevant or not, a narrower skill than the sentence similarity an embedding model
learns, and it returns a single relevance score rather than a vector, so nothing
about it reaches pgvector. Those scores order candidates within one query and
mean nothing across queries.

It replaces the six-layer model of the same family, which shares its training
data and its width and differs only in depth. The smaller one was demoting
correct documents that fusion had already ranked first, on questions phrased the
way viewers ask rather than the way MS MARCO queries are written. Doubling the
depth answers that: MRR 0.818 to 0.853, hit rate at one 0.758 to 0.816, paired
interval clear of zero. Public benchmarks already ranked the two in this order,
so the result is a confirmation rather than a discovery; what it demonstrated is
the split and the intervals working end to end on a live decision.

BAAI's own `bge-reranker-base` would match the encoder's family but is built on
multilingual XLM-RoBERTa and ships 1.1 GB of weights for languages this corpus
does not contain. English, CPU-sized, and ONNX-published are the properties that
matter here; a shared family name is not one of them.

Reranking itself is adopted on its own comparison against the hybrid baseline,
which it wins by 0.095 MRR. It is the largest effect measured on this corpus and
the only extra that is not close. Every answer therefore goes through it,
switched on where the agent's tool calls search rather than chosen by the model,
for the reason the spoiler boundary is not an argument either.

Reranking is the slowest part of a search, and the deeper model is slower again.
That is affordable beside the model call which follows it, and the shortlist of
twenty units is the lever if it ever stops being.

## Where query rewriting happens

The agent writes the query. It receives the conversation and composes the words
it passes to the search tool, so a question referring back to an earlier turn is
resolved inside a call that was happening regardless, and a viewer's loose
description is turned into the series' own terms. That is query rewriting, done
by the loop rather than by a stage in front of it.

No separate rewriting component sits between the user and search. One would add a
component and a frozen artifact to maintain, spend a model call on every turn
whether or not the question needed one, and place a second non-deterministic step
beside measurements whose value is that a later run compares to an earlier one.

What the rewriting costs is measured rather than assumed. Over the same
questions, the agent's own queries reach the answering document about six points
less often than the question searched verbatim, because a paraphrase discards the
names the documents match on. The instructions therefore send the question
unchanged on the first search and let the model rewrite on any search after it,
which keeps what rewriting is good at without paying for it on the one search
that needed no help. [Agent](agent.md) owns those instructions and
[Evaluation](evaluation.md) owns the comparison.
