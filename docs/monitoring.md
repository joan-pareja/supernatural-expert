---
type: reference
title: Monitoring
description: Defines Logfire as the single telemetry and feedback source.
status: approved
modified: 2026-08-13T17:01:00+02:00
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
user feedback. Pydantic AI instrumentation covers agent and model calls, and
attributes on the spans it already opens cover what it cannot explain by itself.

`supernatural_expert.monitoring.telemetry` configures Logfire and instruments the
agent. Configuring is process-wide, so it happens at an entry point and nowhere
else: the command line before it answers, and the chat inside the cached loader
that Streamlit runs once per server rather than once per rerun.

Instrumentation covers the model call, the tool call, the token usage, and the
timing of each. The tool span already carries the arguments the model chose and
everything the search returned, and it lasts as long as the search inside it, so
a span of its own around that call would repeat both.

What instrumentation cannot know is how the search was run and how it ended up
ranked. Every search therefore adds `search.path`, `search.rerank`,
`search.limit`, and `search.documents` to whichever span is running. The last of
those lifts the ranked identifiers out of the returned documents, so a query
across traces reads an array instead of parsing five episode plots.

Those attributes rather than a span name are what a query keys on, because a turn
holds two kinds of search. The tool call the model makes lands on the span
Pydantic AI already opened for it. The verbatim first search runs before the
agent and outside it, as [Agent](agent.md) describes, so no instrumentation sees
it and the application opens `search_episodes verbatim` around it. The rule is
unchanged rather than bent: nothing opens a second span over work the library
already covers, and this is work it never sees. A query filtering on
`search.path` reads both.

The chat turn is the only other span the project opens, and it exists for
feedback rather than for telemetry.

## Feedback

The chat draws a thumb under every answer and sends the click through
`logfire.experimental.annotations.record_feedback`, which writes an annotation
under the turn it judges rather than a log line beside it. Logfire recognises the
`logfire.feedback.name` attribute it carries, so a judged run is queryable and
readable as one thing. PostgreSQL must not keep a duplicate feedback copy.

Reaching that turn is the whole difficulty. A thumb is clicked on a later
Streamlit rerun, when every span the answer opened has closed and none is
reachable, so the chat opens one span per turn and keeps its traceparent beside
the message. That span is also the turn as the viewer experiences it, which the
agent run inside it is not.

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

The dashboard is `Supernatural Expert`, and `monitoring/dashboard.json` is the
definition it was created from. Six panels:

1. Questions answered over time, every agent run against the chat turns among
   them.
2. Turn and model latency, at the median and the 95th percentile, which is what
   separates a slow system from a slow model inside it.
3. Thumbs up against thumbs down.
4. Judge verdicts, as the share of judged answers passing each measure.
5. Model cost over time, split by model.
6. Tokens and cost per model, as a table.

The judge panel reads the evaluation runs rather than the chat. Judging is an
offline measurement and nothing grades a live answer, so what a viewer sends is
read through the thumb beside it. Both land in the same project, which is what
lets one dashboard show them together.

They are drawn in Logfire. Every one of these views reads spans the app already
sends, so a dashboard there is a view over data in place, where a Streamlit
reporting page would cost a read credential, a query client, and a second page to
show the same numbers. A chart Logfire does not offer ready-made is built as a
custom chart inside Logfire rather than outside it.

The chat therefore has no reporting page, and the running application needs no
read credential.

These are the panels populated, so a peer reviewer sees the evidence without the
project's private Logfire access.

![Traffic and latency](images/dashboard__traffic-and-latency.png)

![Quality and cost](images/dashboard__quality-and-cost.png)

Reading the traces while building is a separate matter from serving them. Logfire
publishes an MCP server, and connecting it lets a coding agent query spans
directly instead of reading a dashboard after the fact: a turn that spent six
searches on one question was found that way, a search that looked
catastrophically slow turned out to be a single stalled query rather than the
reranker, and every cost figure in [Journey](../JOURNEY.md) was read from spans
rather than estimated. That read token belongs to whoever is developing, lives in
their shell, and never enters the repository or the application's settings.

## Seeing it on your own project

Telemetry is off until a write token is set, so the views above are empty for
anyone who has not connected a project of their own. Five steps connect one:

1. Create a free project at [logfire.pydantic.dev](https://logfire.pydantic.dev).
2. In its settings, create a **write token** and copy it.
3. Put it in `.env` as `LOGFIRE_WRITE_TOKEN=`, leaving `LOGFIRE_READ_TOKEN`
   empty; the application never reads that one.
4. Restart the app with `docker compose up -d --force-recreate app`, so the
   container rebuilds the settings file it reads at start.
5. Ask the chat a question and rate the answer. The trace appears within
   seconds, carrying the agent run, both searches, token usage, and cost, with
   the thumb attached to the turn it judges.

The charts come from `monitoring/dashboard.json`, the definition the maintainer's
own dashboard was created from. It carries each panel's SQL, so the six are
rebuilt in a new project either by sending the file to Logfire's dashboard API or
by pasting the queries into custom charts one at a time. Every panel reads spans
the app has by then already sent, so they fill from that first question onward
rather than needing anything further turned on.

## Reviewer evidence

The rubric requires collected feedback and a dashboard with at least five
charts. It does not require access to the author's hosted monitoring account.
The submitted repository will provide:

- the feedback and telemetry code;
- the six charts, as the Logfire dashboard definition in `monitoring/`;
- screenshots of the populated dashboard;
- steps for a reviewer to connect their own Logfire project and create fresh
  events.

This keeps the implementation inspectable without sharing private Logfire
access or maintaining a second metrics store.

The server needs write credentials for telemetry and nothing else. They belong in
neither the browser nor the repository.

References: [Pydantic AI Logfire integration](https://pydantic.dev/docs/ai/integrations/logfire/),
[Logfire dashboards](https://logfire.pydantic.dev/docs/guides/web-ui/dashboards/),
and [Logfire Query API](https://logfire.pydantic.dev/docs/how-to-guides/query-api/).
