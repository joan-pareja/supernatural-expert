---
type: reference
title: Project scope
description: Defines the problem, audience, and first-release boundary.
status: approved
modified: 2026-07-27T00:22:00+02:00
tags:
- scope
- product
related:
- ../README.md
- ./corpus.md
---

# Project scope

> Keep the product goal and first-release boundary here. Do not turn this into a
> feature backlog.

## Goal

The goal is a small expert that answers questions about *Supernatural* episodes
with fresh, inspectable source text. It is meant to be more faithful than asking
a model from memory, and safe for a viewer who has not watched beyond Season 6.

The first idea allowed users to create experts for any movie or show. That made
corpus selection, loading, and setup the main project. The fixed show and spoiler
boundary leave time for the course goals: retrieval, evaluation, feedback,
monitoring, and a reproducible app.

## First release

The release covers English Wikipedia episode information for seasons 1 through
6. A user can ask through Streamlit, inspect source links, and rate the answer.
The agent must stay inside the spoiler boundary, rely on retrieved evidence, and
say when the corpus cannot support an answer.

The project is a two-week course delivery. It favors a clear working path over
production machinery. Local Docker Compose is the delivery target; cloud
deployment is not part of it.

## Success

Success means a reviewer can load the public corpus, run the app, compare tested
retrieval and answer approaches, see monitoring charts, and trace an answer back
to Wikipedia.
