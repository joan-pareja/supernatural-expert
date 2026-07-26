---
type: reference
title: Wikipedia extraction alternatives
description: Compares the wikitext parser against libraries, parse trees, Wikidata, and Parsoid.
status: approved
modified: 2026-07-26T21:00:00+02:00
tags:
- ingestion
- wikipedia
- wikitext
- research
related:
- ../ingestion.md
- ../corpus.md
---

# Wikipedia extraction alternatives

> Records what else could have produced the corpus, and why the current
> approach stands. Parsing rules stay in `wikitext.py`; this file only compares
> mechanisms.

## What was checked

Every claim below was taken from the interface that owns it: the MediaWiki
Action API help, the two libraries' own repositories and package metadata, the
Wikidata Query Service, and live responses from `en.wikipedia.org`. Live calls
used revision 1357856174 of `Supernatural season 1`, section 5 (`Episodes`),
resolved by the same three requests the pipeline makes.

## The three hard cases

These are the constructs that force depth-aware splitting.

| Case | Example |
| --- | --- |
| Pipe inside a link | `Title = [[Pilot (Supernatural)\|Pilot]]` |
| Pipes and equals inside a nested template | `WrittenBy = {{StoryTeleplay\|s=…\|t=…}}` |
| Nested template inside a ref tag | `Viewers = 5.69<ref>{{#invoke:cite\|web\|url=…}}</ref>` |

## Preprocessor XML: `action=parse&prop=parsetree`

The Action API can return the preprocessor's own parse tree instead of raw
wikitext. It is documented as "The XML parse tree of revision content (requires
content model `wikitext`)"
([API help](https://en.wikipedia.org/w/api.php?action=help&modules=parse)).

It combines with `oldid` and `section`, so the pipeline's existing pinning and
section discovery would carry over unchanged, and the response still carries
`revid` alongside `parsetree`. A live call on the season 1 `Episodes` section
returned this, with names, equals signs, and values already separated:

```xml
<part><name> WrittenBy </name><equals>=</equals><value>
  <template><title>StoryTeleplay</title>
    <part><name>s</name><equals>=</equals><value>Ron Milbauer &amp; Terri Hughes Burton</value></part>
    <part><name>t</name><equals>=</equals><value>Eric Kripke</value></part>
  </template>
</value></part>
```

All three hard cases are handled. Nested templates become nested `<template>`
elements, ref tags become `<ext>` elements with their contents in `<inner>`, and
positional arguments are marked `<name index="1"/>`. That would remove the
depth-tracking splitters outright, using only `xml.etree` from the standard
library, so no new dependency.

Two limits matter. Wikilinks are **not** nodes: `[[Pilot (Supernatural)|Pilot]]`
arrives inside `<value>` as plain text, so depth-aware splitting is still needed
to resolve links. And the payload is larger: 61,584 bytes of XML against 40,530
bytes of wikitext for the same section.

`action=expandtemplates` also offers `prop=parsetree`, described as "The XML
parse tree of the input"
([API:Expandtemplates](https://www.mediawiki.org/wiki/API:Expandtemplates)). It
takes text rather than a page, so it adds nothing here; its older
`generatexml` parameter is deprecated in favour of `prop=parsetree`.

Neither page marks `prop=parsetree` deprecated or experimental. Neither promises
stability either. It is the preprocessor's internal shape, exposed.

## mwparserfromhell

Source and metadata:
[repository](https://github.com/earwig/mwparserfromhell),
[PyPI](https://pypi.org/project/mwparserfromhell/).

| Property | Value |
| --- | --- |
| Latest release | 0.7.2, uploaded 2025-07-01 |
| Maintained | Yes; repository last pushed 2026-07-25 |
| Licence | MIT |
| Runtime dependencies | None |
| Type hints | Ships `py.typed`; checked with Pyright upstream |
| Implementation | C tokenizer with a pure-Python fallback |
| Windows wheels | `cp39`–`cp313`, `win32` and `win_amd64` |

It handles all three hard cases. Ref tags are tokenised as `Tag` nodes with
their contents parsed, so pipes inside a ref never reach template-parameter
splitting; the library's own integration tests cover a ref tag whose attributes
and body are full of templates and links. Access is
`template.get("ShortSummary").value`, and `Template.get` returns the last
parameter with that name, matching MediaWiki's own precedence rule.

Windows 10 is fine today. The project pins CPython 3.13, and a `cp313
win_amd64` wheel exists. Note the failure mode if that ever stops being true:
on CPython, `setup.py` marks the extension **required**, so a source build with
no compiler fails rather than falling back. The fallback needs
`WITH_EXTENSION=0` set explicitly. There is no `cp314` wheel for 0.7.2.

Where it stops short is cleaning. `strip_code` removes templates and keeps link
text, which matches `_drop_templates` and `_resolve_links`. But two behaviours
differ from what the corpus needs:

- Ref tags are **not** in the library's `INVISIBLE_TAGS`, so `Tag.__strip__`
  returns the ref's contents. `<ref>{{#invoke:cite|…}}</ref>` collapses to
  nothing because its body is a template, but `<ref>Knight, p. 66</ref>`
  survives as prose. Seasons 1, 2 and 3 carry 56, 54 and 53 such plain-text
  refs respectively across their pages. None fall inside the sections the
  pipeline ingests today, but `strip_references` is what guarantees that.
- File links get no special treatment. `Wikilink.text` is everything after the
  first pipe, so `[[File:x.jpg|thumb|caption]]` strips to `thumb|caption`
  rather than being dropped whole.

## wikitextparser

Source and metadata:
[repository](https://github.com/5j9/wikitextparser),
[PyPI](https://pypi.org/project/wikitextparser/).

| Property | Value |
| --- | --- |
| Latest release | 1.0.2, uploaded 2026-06-25 |
| Maintained | Yes; repository last pushed 2026-07-18 |
| Licence | GPL-3.0 |
| Runtime dependencies | `regex`, `wcwidth` |
| Type hints | Annotated, but ships **no** `py.typed` marker |
| Implementation | Pure Python, `py3-none-any` wheel |

It handles all three hard cases as well, exposing `Template.arguments` with
`Argument.name`, `Argument.value` and `Argument.positional`, plus
`Template.get_arg(name)` returning the last match.

Its `plain_text` is closer to `clean_text` than mwparserfromhell's `strip_code`
is: one call removes comments, templates, parser functions, parameters, tags,
bracketed external links, bolds and italics, resolves wikilinks, drops image
links by file extension, and unescapes HTML entities. `replace_templates` and
`replace_parser_functions` accept callables, so `{{Start date}}` could be mapped
to a date string in place rather than read separately.

It shares the ref problem, and more visibly: `replace_tags` removes only the tag
markup and keeps the contents, so every ref body becomes prose.

Two costs weigh against it here. GPL-3.0 is a stronger licence obligation than
this project otherwise carries. And with no `py.typed` marker, a `strict`
Pyright configuration sees its API as untyped, which means `Unknown` types
spreading through the call sites.

## Library comparison

| | mwparserfromhell | wikitextparser | `prop=parsetree` |
| --- | --- | --- | --- |
| Pipe in link | Yes | Yes | Split still needed |
| Nested template params | Yes | Yes | Yes |
| Template inside ref | Yes | Yes | Yes |
| Extra dependencies | 0 | 2 | 0 |
| Licence | MIT | GPL-3.0 | n/a |
| Typed for strict Pyright | Yes | No | n/a |
| Pure Python on Windows | Wheels, else compiler | Yes | n/a |
| Removes ref bodies | No | No | Marks them as `<ext>` |
| Drops file links | No | Yes | No |

## Wikidata

Supernatural episodes are modelled. The series is
[Q130585](https://www.wikidata.org/wiki/Q130585) and season 1 is
[Q1223181](https://www.wikidata.org/wiki/Q1223181). A single query against
[query.wikidata.org](https://query.wikidata.org/) returns all 22 season 1
episodes with ordinal, air date, director and screenwriter:

```sparql
SELECT ?ep ?epLabel ?ord ?date
       (GROUP_CONCAT(DISTINCT ?dl;separator=", ") AS ?dirs)
       (GROUP_CONCAT(DISTINCT ?wl;separator=", ") AS ?wris) WHERE {
  ?ep p:P4908 ?st . ?st ps:P4908 wd:Q1223181 .
  OPTIONAL { ?st pq:P1545 ?ord }
  OPTIONAL { ?ep wdt:P577 ?date }
  OPTIONAL { ?ep wdt:P57 ?d . ?d rdfs:label ?dl FILTER(lang(?dl)="en") }
  OPTIONAL { ?ep wdt:P58 ?w . ?w rdfs:label ?wl FILTER(lang(?wl)="en") }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
}
GROUP BY ?ep ?epLabel ?ord ?date
ORDER BY xsd:integer(?ord)
```

The episode number is a qualifier on the season statement, not a direct claim;
querying `wdt:P1545` alone returns nothing.

The results are usable for numbering and dates but not for credits. Every
season 1 episode lists Eric Kripke as screenwriter, including "Wendigo", whose
table entry is `{{StoryTeleplay|s=Ron Milbauer & Terri Hughes Burton|t=Eric
Kripke}}`. Wikidata has no story-versus-teleplay distinction, so the split
credit the pipeline reconstructs is simply absent.

There is no plot prose. A full claim dump of one episode
([Q465349](https://www.wikidata.org/wiki/Q465349)) returns 20 properties, none
of them a summary, and no viewer figures. Its English description is the string
`episode of Supernatural`. **Wikidata can replace at most the metadata half; it
cannot supply `content`, which is the only field the corpus indexes.**

## Parsoid HTML and the REST APIs

Both the Wikimedia REST API
(`/api/rest_v1/page/html/{title}/{revision}`) and the newer Core REST API
(`/w/rest.php/v1/revision/{id}/html`) return the same Parsoid document,
labelled `profile="https://www.mediawiki.org/wiki/Specs/HTML/2.8.0"`. Both
accept a revision ID. Neither returns a single section.

The expected trade-off — real `<table>` structure but no named parameters — does
not hold. Parsoid preserves the full template call in `data-mw`:

```json
{"template":{"target":{"wt":"Episode list/sublist"},
 "params":{"EpisodeNumber2":{"wt":"1"},
           "Title":{"wt":"[[Pilot (Supernatural)|Pilot]]"},
           "OriginalAirDate":{"wt":"{{Start date|2005|9|13}}"}}}}
```

Named parameters survive, but their values are raw wikitext under a `wt` key.
That means the same cleaning problem, now reached through JSON embedded in an
HTML attribute. [Specs/HTML](https://www.mediawiki.org/wiki/Specs/HTML)
describes `data-mw` as "meant as an extensible public interface" while marking
`data-parsoid` as internal, so the interface is documented, but the same spec
warns that the representation of magic variables and parser functions "is
expected to change in the next major revision".

The cost is size. The season 1 page is 431,430 bytes of Parsoid HTML against
40,530 bytes for the one section actually needed: roughly ten times the payload
for a strictly harder parse.

## Other official mechanisms

- **TemplateData** documents a template's parameter schema for editing
  interfaces. It carries no per-page values, so it cannot extract anything.
- **Wikimedia Enterprise API** offers snapshot, on-demand and realtime feeds
  with a freemium account. It is built for bulk consumers of whole projects;
  132 documents fetched once do not justify an account, and its Structured
  Contents feature is beta.
- **Database dumps** move the same wikitext problem to a multi-gigabyte file
  with no revision pinning benefit over the Action API.

## Recommendation

**(a) Keep the hand-rolled parser as-is.**

The reasoning is narrow rather than defensive. Every alternative addresses the
splitting half of the problem and none addresses the cleaning half. Both
libraries keep ref bodies, so `strip_references` survives a swap in any case.
`prop=parsetree` still leaves wikilink resolution to hand-written depth
tracking. Parsoid returns the same unparsed wikitext values ten times more
expensively. Wikidata cannot supply `content` at all, and its credits are
demonstrably less accurate than the table the pipeline already reads.

So the honest scope of the saving is roughly 90 of the module's 320 lines —
`_skip_markup`, `_split_at_depth`, `_partition_at_depth`, `iter_template_bodies`
and `template_fields` — against a working, dependency-free, strictly typed
module covering a fixed 132-document corpus with 27 tests. That is not a trade
worth making now.

Two things are worth knowing rather than acting on.

First, had this been a greenfield decision, mwparserfromhell was the right
default: MIT, zero runtime dependencies, `py.typed`, Windows wheels for the
pinned interpreter, and correct on all three hard cases. The cleaning rules in
`clean_text` would have been written either way. Recording that keeps the
decision honest rather than lucky.

Second, `action=parse&prop=parsetree` is the escape hatch if the season pages
ever adopt template shapes the splitters mishandle. It needs no new dependency,
works with the `oldid` and `section` parameters already in use, and still
returns `revid`, so provenance is unaffected.
