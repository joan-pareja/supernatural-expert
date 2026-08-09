---
type: reference
title: Agent
description: Defines the answering loop, its search tool, and what an answer may claim.
status: approved
modified: 2026-08-09T23:45:00+02:00
tags:
- agent
- pydantic-ai
- grounding
related:
- ./retrieval.md
- ./monitoring.md
- ../ARCHITECTURE.md
---

# Agent

> Keep answering behavior here. [Retrieval](retrieval.md) owns how search itself
> works, and this document does not restate it.

## The loop

Pydantic AI owns the loop. The model receives the question and one tool, decides
whether to search and with what wording, reads what comes back, and searches
again when the results do not settle the question. Nothing in the application
schedules those calls or caps them by hand.

What the model is told about that wording is the one lever over it. A viewer
describes things loosely and the documents carry the show's own names, so the
instructions ask for a query written in the series' vocabulary rather than the
question's. Neither search path can bridge that gap on its own: a rephrasing is
not a synonym either ranking can see.

The loop is synchronous. PostgreSQL access and ONNX inference both block, so an
asynchronous agent would wait on the same work through more machinery, and the
choice would spread to every caller including Streamlit.

## The search tool

One tool, `search_episodes`, running hybrid RRF search. The path is fixed rather
than offered to the model: choosing between lexical, vector, and hybrid is a
measured decision, and a model picking per question would make every measurement
describe a setup that no longer exists.

The tool takes the query and, optionally, a season and an episode number. Those
narrow the search and enforce nothing, which is the same contract every caller
of search gets. The model is told to leave them unset unless the question names
one, because a wrong guess hides the answer rather than sharpening it.

It returns whole documents, five of them. Each carries an episode plot, so the
count is a context budget as much as a recall setting.

## The answer as a schema

The answer type is not only a return type. Pydantic AI turns it into a tool the
model has to call to finish, so its field names, types, and descriptions are the
last thing the model reads before writing. `Annotated` carries a description on
each field, which is where narrow rules belong: that a citation is an identifier
and never a title or a URL, and that it is empty when the corpus does not answer.
A rule stated beside the field it governs competes with nothing, where the same
sentence in the instructions competes with every other sentence there.

Docstrings on anything the model touches are therefore prompt, and are written
for it. What only a reader of the module needs, such as how a citation is
resolved back to a link, sits in comments beside the code instead. Every call
pays for the schema, and the model cannot act on our plumbing anyway.

## Citations

An answer carries the identifiers of the documents it rests on, and the
application resolves each one to a title and a Wikipedia link. The model never
writes a URL and so cannot write a wrong one.

Every identifier is checked against what the run actually retrieved. A citation
for anything else fails validation and the answer goes back to the model, which
sees which identifiers were invented. This is the part of grounding that does not
depend on the model cooperating: a model that has read five documents can still
cite a sixth it remembers, and a citation is worth what the guarantee behind it
is worth.

The other part does depend on cooperation. The instructions say to write only
from what search returned, and no check can confirm that a sentence came from a
retrieved document rather than from memory. Which is why the answer setups
compared in [Evaluation](evaluation.md) are judged on support as well as
relevance.

## Abstention and spoilers

The agent says the corpus does not cover a question, and cites nothing, rather
than closing the gap from what it knows about the show. An empty search result is
an answer about the corpus, not a reason to fall back on the model.

The spoiler boundary is the corpus, as [Retrieval](retrieval.md) explains: seasons
past 6 were never loaded, so there is nothing to filter. What remains for the
agent is the question the corpus cannot answer at all, which is a request for a
spoiler and is refused as one. The model plainly knows how the series continues,
so this is the one instruction that has to hold against its own knowledge.

## Model

`gpt-5.4-mini` answers, through `pydantic-ai-slim[openai]`. The key is passed to
the provider explicitly, so the OpenAI SDK never reads it from the process
environment, as every other client here is passed its credentials. It is the only
credential the application requires, and it is required where an answer is
written rather than where settings are read, so loading and indexing the corpus
work without one.
