---
type: reference
title: Monitoring
description: Defines Logfire as the single telemetry and feedback source.
status: approved
modified: 2026-08-10T01:52:00+02:00
tags:
- monitoring
- logfire
- dashboard
related:
- ../ARCHITECTURE.md
- ./evaluation.md
- ./rubric.md
---

# Monitoring

> Keep observable events and reporting needs here. Do not create a second
> metrics store.

Pydantic Logfire is the one source for traces, usage, errors, judge results, and
user feedback. Pydantic AI instrumentation covers agent and model calls. Small
custom spans cover retrieval and other app work that automatic instrumentation
cannot explain.

`supernatural_expert.monitoring.telemetry` configures Logfire and instruments the
agent. Configuring is process-wide, so it happens at an entry point and nowhere
else: the command line before it answers, and the chat inside the cached loader
that Streamlit runs once per server rather than once per rerun.

Instrumentation covers the model call, the tool call, the token usage, and the
timing of each. The tool span already carries the arguments the model chose and
everything the search returned, and it lasts as long as the search inside it, so
a span of its own around that call would repeat both.

What instrumentation cannot know is how the search was run and how it ended up
ranked. `search_episodes` therefore adds `search.path`, `search.rerank`, and
`search.documents` to the span already covering it. The last of those lifts the
ranked identifiers out of the returned documents, so a query across traces reads
an array instead of parsing five episode plots. The project opens no spans of its
own.

Thumbs-up and thumbs-down actions are structured Logfire events tied to the run
and answer. PostgreSQL must not keep a duplicate feedback or monitoring copy.

## What is sent

A trace carries the question, the retrieved text, and the answer, so questions
asked of the chat leave the machine when a token is set. The corpus is public
Wikipedia and the project is a personal one, so this costs nothing worth
protecting and is what makes a trace worth reading at all.

## Optional by design

Logfire is configured with `send_to_logfire="if-token-present"`. With a write
token the app sends telemetry; without one it sends nothing, raises nothing, and
runs normally.

Logfire is therefore optional for anyone running the project. A reviewer needs
only `OPENAI_API_KEY` to use the chat. Supplying their own Logfire tokens is what
turns telemetry on and lets them reproduce the dashboard; skipping them costs the
monitoring views and nothing else.

## Reporting

The Streamlit reporting page reads Logfire through its Query API and shows at
least these five charts:

1. Requests over time.
2. Positive and negative feedback.
3. Answer relevance from the live judge.
4. End-to-end and model latency.
5. Token use and estimated model cost.

Errors or spoiler refusals may be a sixth view. The final README should include
a dashboard screenshot so peer reviewers can see the evidence even without the
project's private Logfire access.

## Reviewer evidence

The rubric requires collected feedback and a dashboard with at least five
charts. It does not require access to the author's hosted monitoring account.
The submitted repository will provide:

- the feedback and telemetry code;
- the five chart queries and rendering code;
- screenshots of the populated dashboard;
- steps for a reviewer to connect their own Logfire project and create fresh
  events.

This keeps the implementation inspectable without sharing private Logfire
access or maintaining a second metrics store.

The server needs write credentials for telemetry and a read token for reporting.
Neither belongs in the browser or repository.

References: [Pydantic AI Logfire integration](https://pydantic.dev/docs/ai/integrations/logfire/),
[Logfire dashboards](https://logfire.pydantic.dev/docs/guides/web-ui/dashboards/),
and [Logfire Query API](https://logfire.pydantic.dev/docs/how-to-guides/query-api/).
