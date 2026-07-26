---
type: reference
title: Project context
description: Defines words that have a special meaning in Supernatural Expert.
status: approved
modified: 2026-07-26T22:45:00+02:00
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

**Corpus document**  
One cleaned, searchable record. It contains one final `content` field and its
Wikipedia provenance. Every document is an episode document or a season
introduction document.

**Episode document**  
The one corpus document for an episode.

**Season introduction document**  
The one corpus document for a season, holding its Wikipedia lead section. It
answers questions about a season as a whole, which no episode document can.

**Season table summary**  
The episode description inside a Wikipedia season page's episode table.

**Standalone episode article**  
A separate Wikipedia page for one episode, such as `Pilot (Supernatural)`.

**Standalone plot**  
The Plot section taken from a standalone episode article. When present, it
replaces the shorter season table summary as the episode document's content.

**Corpus**  
The fixed set of corpus documents for *Supernatural* seasons 1 through 6.
