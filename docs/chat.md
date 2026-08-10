---
type: reference
title: Chat
description: Defines the Streamlit page, what it keeps between reruns, and how it looks.
status: approved
modified: 2026-08-10T02:18:00+02:00
tags:
- streamlit
- chat
- ui
related:
- ./agent.md
- ./monitoring.md
- ../ARCHITECTURE.md
---

# Chat

> Keep the browser surface here. [Agent](agent.md) owns what an answer may claim,
> and this document does not restate it.

## The page

One page, `src/supernatural_expert/chat/app.py`, run with `uv run streamlit run
src/supernatural_expert/chat/app.py`. It asks questions, shows answers with their
sources, and takes a thumb on each one. Reporting is not here, and where it lands
is [Monitoring](monitoring.md)'s to settle.

The thumbs are Streamlit's own `st.feedback` widget rather than a pair of
buttons, so the page ships no icons and no state of its own for them: the widget
remembers which thumb was pressed, and the click is sent once, on the rerun that
changed it. Where it is sent is [Monitoring](monitoring.md)'s.

Streamlit reruns the whole file on every interaction. The page is therefore drawn
from state rather than mutated: the conversation is a list in `st.session_state`,
and each rerun redraws it from the top.

## What survives a rerun

Loading settings, building the model, and opening the PostgreSQL connection all
cost seconds and none of them varies by question. They are built once behind
`st.cache_resource`, which is why the command-line entry point pays that cost per
question and the chat pays it once per server. The connection is never closed; it
lives as long as the server.

The cached engine is shared by every browser session, and Streamlit runs each
session in its own thread. Search is not thread-safe, because the encoder is not,
so answers are taken one at a time under a lock.

Two things are per session instead. The message history is passed back to the
agent on every turn, which is what lets a follow-up say "that episode". The
agent's dependencies are rebuilt for each question, so a citation is checked
against the documents that question retrieved rather than an earlier one's.

## Appearance

`.streamlit/config.toml` carries the whole look through Streamlit's own theme
options, so the app ships no CSS and nothing depends on Streamlit's internal
class names.

The palette is a soft blue on a near-white background, with borders a shade
lighter than the text is dark. Blue reads as steady rather than urgent, which is
what an answer with sources should look like. The theme fixes a light base rather
than following the viewer's dark mode, because the palette is chosen against a
light background and half of it would be unreadable inverted.

Corners are rounded everywhere, fully so on buttons. Sources sit in a collapsed
expander under each answer rather than beside it, so the conversation reads as
prose and the evidence is one click away.
