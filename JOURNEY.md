---
type: reference
title: Journey
description: How the project reached its current shape, and what each turn was worth.
status: approved
modified: 2026-08-11T01:32:00+02:00
tags:
- journey
- decisions
- results
related:
- ./docs/rubric.md
- ./docs/evaluation.md
- ./docs/retrieval.md
---

# Journey

> The short version of how this was built and why. [Rubric](docs/rubric.md)
> tracks what is scored; this note explains what happened. Every section links
> to the document that owns the detail, so nothing here needs to be long.

## The problem

An expert that answers only from an approved corpus. Not from the internet, and
not from whatever the model happens to remember. Answers come from documents the
project chose, which makes them consistent, cheap, and checkable.

The first idea was to pull a corpus on demand for whichever show a viewer picked.
It would have worked, and it would have kept working past any model's knowledge
cutoff. It was dropped because the project would have become an ingestion
ceremony rather than a retrieval system. One show is locked instead:
*Supernatural*, seasons 1 to 6.

Locking it bought more than focus. A corpus that never changes can have a fixed
set of test questions, and fixed questions are what make every measurement below
comparable to the one before it. The scoping decision and the evaluation
discipline are the same decision seen twice.

Spoiler safety falls out of the same choice. Seasons past 6 were never loaded, so
there is nothing to filter and nothing to leak — a question about season 7 is one
the corpus cannot answer, and is refused as such.

See [Scope](docs/scope.md).

## Getting the corpus in

Wikipedia stores episode data as wikitext templates, which are awkward: values
contain nested links, templates, and citations, so naive splitting corrupts them.
Existing parsing libraries were compared before anything was written; the finding
is in [Wikipedia extraction alternatives](docs/research/wikipedia-extraction-alternatives.md).
A small purpose-built parser won, because the corpus is fixed and small and the
library would have brought more surface than it removed.

**The turn that mattered:** episodes alone could not answer questions about a
season. Adding one introduction document per season took the corpus from 126
documents to 132, and it shaped everything downstream — those six documents are
long, prose-heavy, and nearly identical to each other, which is a problem both
chunking and retrieval had to deal with later.

The load runs through **dlt**, in one command, from pinned revisions.

See [Ingestion](docs/ingestion.md) and [Corpus](docs/corpus.md).

## Embeddings and chunking

The course's default embedding model was replaced with `bge-small-en-v1.5`,
chosen on published retrieval benchmarks rather than on this project's own
questions — a model this small should not be selected using the same data used to
judge everything else.

**The turn that mattered:** the model's published tokenizer configuration capped
input at 128 tokens. Left alone, 131 of the 132 documents would have been
embedded from a fraction of their text, silently, with no error anywhere. Fixing
it to the model's real window is what made chunking necessary and worthwhile:
documents are now split to fit that window, turning 132 documents into 173
searchable units.

See [Retrieval](docs/retrieval.md).

## Search, and the change that reset everything

Three retrieval paths were built before any was chosen: lexical, vector, and a
hybrid that fuses both with reciprocal rank fusion at the constant its paper
publishes, left untuned.

**The turn that mattered:** the first evaluation showed lexical search finding
almost nothing — the right document came back for **8 of 426** questions.
PostgreSQL's built-in text ranking scores only within a document, so a word in
nearly every episode counted as much as a rare one, and its query builder
required every term to match. Replacing it with **BM25** took the same measurement
to **400 of 426**. Nothing else in the project moved a number that far.

It also changed what the other results meant. Before, hybrid was
indistinguishable from vector alone. After, lexical was the stronger single path,
and fusing the two beat both.

**Reranking was never in the plan.** It was added after the paths were settled,
reading the top twenty results with a cross-encoder that scores each one against
the question directly. It earned its place: MRR 0.808 to 0.881.

**Optuna was in the plan, and was dropped.** Once the paths were measured, every
parameter it would have searched turned out to be settled already — the fusion
constant by its paper, the candidate depth by a corpus of 132 documents, and the
one dial that would have moved the result is exactly the dial a few hundred
questions can be fitted to rather than measured by.

**Query rewriting is not a separate stage, because the agent already does it.**
It composes the words it sends to search rather than passing the question
through. That was measured too — see below.

## How anything gets decided

Every choice above rests on the same machinery, built once.

**426 questions**, generated from the corpus, each labelled with the one document
that answers it, covering all 132 documents.

**Split by document, not by question.** A fifth of the documents are held out, so
questions about one episode can never land on both sides. The split is seeded and
committed, and a test regenerates it to prove the committed file is the one the
seed produces.

**Setups are compared question by question.** Two setups answer the same
questions, the results are subtracted per question, and the confidence interval
is drawn over those differences. This is sharper than comparing two averages,
because a question hard for one setup is usually hard for both and subtracting
removes the difficulty they share. An interval that still contains zero is a tie,
and a tie goes to the simpler setup.

**The held-out side answers one question, once:** does the winner hold up on
documents no comparison ever saw? It is never used to choose between setups,
because a set used to choose is no longer a set that can check the choice.

Two later corrections came out of using it:

- **The questions were rewritten** to sound like viewers rather than exam papers,
  with at least one question per document carrying no proper noun at all. The
  originals leaned on rare names, which flattered lexical search. Removing that
  lean cost lexical 0.14 MRR and vector 0.05 — the advantage was real and was
  never earned. Labels, counts, and the held-out split were untouched, no setup
  was compared during the rewrite, and scores from before it do not compare to
  scores after.
- **One question was found answerable by two documents** and relabelled, and a
  handful phrased too vaguely for any retriever were fixed.

See [Evaluation](docs/evaluation.md).

## What the numbers say

Five setups, 343 tuning questions. Hit@1 is how often the right episode came back
first; MRR is how high up it landed on average.

| Setup | hit@1 | hit@5 | MRR |
|---|---|---|---|
| lexical | 0.554 | 0.784 | 0.654 |
| vector | 0.519 | 0.711 | 0.604 |
| hybrid | 0.633 | 0.837 | 0.724 |
| hybrid + reranking | 0.758 | 0.895 | 0.818 |
| **hybrid + deeper reranking** | **0.816** | **0.910** | **0.853** |

Each setup was measured against the simpler one it had to beat, and every step
cleared its interval: fusing beats lexical alone by 0.070, reranking beats fusion
by 0.095, and the deeper cross-encoder beats the smaller one by 0.035.

The last of those was the first full use of the machinery: two models, compared
on the tuning side, winner adopted, then read once against the held-out
documents. **Tuning 0.853, held-out 0.855.** A gap of 0.001 says the score was
not inflated by having chosen the winner on those questions.

Worth being honest about that comparison: public benchmarks already rank these
two cross-encoders in the same order, so the result was not a discovery. What it
demonstrated is that the split, the paired intervals, and the held-out
confirmation work end to end on a real decision.

Full tables: [`retrieval_scores.csv`](evaluation/results/retrieval_scores.csv),
[`retrieval_differences.csv`](evaluation/results/retrieval_differences.csv), and
[`retrieval_held_out.csv`](evaluation/results/retrieval_held_out.csv).

## The agent

**Pydantic AI** runs the loop, and one choice earned four things: it schedules the
search calls, turns the search function into a typed tool the model can call,
parses the answer into a validated structure, and wires into Logfire with a
single line.

The model gets one tool, `search_episodes`, with optional season and episode
filters it is told to leave alone unless the viewer names one — a wrong guess
hides the answer rather than narrowing to it.

**Instructions worth naming:**

- The first search sends the question word for word. Measurement showed the
  agent's own phrasing reaches the answering document about six points less often
  than the question as asked, because a paraphrase drops the names the documents
  match on.
- Every search after the first may be rewritten freely into the show's own
  vocabulary, which is what finds an episode a viewer described loosely.
- Answers cite the documents they rest on, and every citation is checked against
  what that run actually retrieved. A model that has read five documents can
  still cite a sixth it remembers; this is the part of grounding that does not
  depend on the model cooperating.
- What the corpus does not cover is said plainly, with nothing cited.

See [Agent](docs/agent.md).

## Judging the answers

Retrieval scores measure search. They do not measure whether the answer was any
good, so two answer setups were compared over 70 questions, judged for whether
they addressed the question and whether every claim appeared in the documents
cited with it.

The setups differ in one thing: how many documents an answer is written from,
five or three.

**Every measure tied.** Which means three documents ships, because a tie goes to
the simpler setup — and three cuts roughly **40% of the tokens** each answer
costs, with no measurable loss in quality. Since answering is where nearly all of
this project's running cost sits, that is the most valuable result in the
document.

> **Not yet re-measured.** These numbers predate the question rewrite and the
> verbatim-first-search change, both of which affect them. The comparison is
> expected to hold and has to be re-run before it can be claimed.

See [Evaluation](docs/evaluation.md).

## The interface

One Streamlit page. It asks questions, shows each answer with the sources behind
it, and takes a thumbs up or down on every one.

See [Chat](docs/chat.md).

## Monitoring

**Logfire, and nothing else.** One place for traces, token usage, errors, and
user feedback, rather than a telemetry tool beside a metrics table that would
drift from it.

**The turn that mattered:** the first instinct was to open a span around each
search. Pydantic AI already opens one for every tool call, covering the same
work and the same duration, so a second span would have recorded the same thing
twice. What instrumentation could not know — which search path ran, whether
results were reranked, which documents came back — was added as attributes on the
span that already existed.

Thumbs feedback is recorded through Logfire's annotations, so a rating attaches
to the run it judges instead of landing in a separate table with no way back to
the answer.

The dashboard is built in Logfire too, for the same reason: every chart reads
spans the app already sends.

> **Not yet built.** Feedback collection is done. The five charts, their
> screenshots, and the steps for a reviewer to point their own Logfire project at
> the app are still outstanding.

See [Monitoring](docs/monitoring.md).

## Reproducibility

Settings are loaded explicitly and passed to every client by hand. Nothing reads
the process environment, so no credential can be picked up by accident and none
can be printed by something that did not expect to hold one.

> **Not yet finished.** A clean Docker Compose run on Windows, pinned dependency
> versions, and tested end-to-end run instructions are outstanding.

## What was left on the table

- **Cloud deployment**, worth two points, is outside the delivery target.
- **A blended ranking** that let fusion keep a vote after reranking was designed
  and not built, because upgrading the cross-encoder fixed the problem it was
  meant to work around.
- **Skipping documents already retrieved** within a turn was considered and
  rejected: a second search is usually a refinement, so hiding the best match
  would hand the model worse results while saving little.
