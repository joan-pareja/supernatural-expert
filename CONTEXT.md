---
type: reference
title: Project context
description: Defines words that have a special meaning in Supernatural Expert.
status: draft
modified: 2026-07-25T19:39:16+02:00
tags:
- glossary
- domain
related:
- ./ARCHITECTURE.md
- ./docs/corpus.md
---

# Project context

> Keep only project-specific language here. General software and AI terms do
> not belong in this glossary.

## Glossary

**Supernatural Expert**  
The app and its Pydantic AI agent.

**Spoiler boundary**  
The end of Season 6. Retrieval and answers must not expose later events.

**Episode document**  
The one cleaned record for an episode. It contains one final `content` field and
its Wikipedia provenance.

**Season table summary**  
The episode description inside a Wikipedia season page's episode table.

**Standalone episode article**  
A separate Wikipedia page for one episode, such as `Pilot (Supernatural)`.

**Standalone plot**  
The Plot section taken from a standalone episode article. When present, it
replaces the shorter season table summary as the episode document's content.

**Corpus**  
The fixed set of episode documents for *Supernatural* seasons 1 through 6.
