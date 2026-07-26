"""Pure wikitext parsing and cleaning.

Nothing here touches the network or the database, so every rule is exercised by
`tests/test_wikitext.py` against fixed samples. Keep it that way: the fetching
code lives in `wikipedia.py`.

Wikipedia's episode tables are templates whose field values contain more
templates, wiki links, and reference tags. Those inner constructs carry their own
`|` and `=` characters, so splitting on those characters directly corrupts the
values. Every splitter below tracks `{{...}}` and `[[...]]` depth and only splits
at depth zero.
"""

import html
import re
from dataclasses import dataclass
from datetime import date

EPISODE_TEMPLATE = "Episode list/sublist"

_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_REF_PAIR = re.compile(r"<ref\b[^>]*?>.*?</ref\s*>", re.DOTALL | re.IGNORECASE)
_REF_SELF_CLOSING = re.compile(r"<ref\b[^>]*?/\s*>", re.IGNORECASE)
_HTML_TAG = re.compile(r"</?[A-Za-z][^>]*>")
_HEADING_LINE = re.compile(r"^\s*=+\s*(.*?)\s*=+\s*$", re.MULTILINE)
_EXTERNAL_LINK = re.compile(r"\[(?:https?:|//)\S+?(?:\s+([^\]]*))?\]")
_BOLD_ITALIC = re.compile(r"'{2,5}")
_BLANK_LINES = re.compile(r"\n{3,}")
_SPACES = re.compile(r"[ \t]+")


class WikitextError(ValueError):
    """Raised when wikitext does not have the shape the pipeline requires."""


@dataclass(frozen=True, slots=True)
class EpisodeListEntry:
    """One `Episode list/sublist` row, cleaned but not yet enriched.

    `standalone_article_title` is set when the Title field links to a separate
    article. It is the link target, while `title` is the displayed episode name;
    the two differ whenever Wikipedia disambiguates, as in
    `[[Pilot (Supernatural)|Pilot]]`.
    """

    series_episode_number: int | None
    season_episode_number: int
    title: str
    standalone_article_title: str | None
    directed_by: str
    written_by: str
    original_air_date: date | None
    production_code: str
    us_viewers_millions: float | None
    season_table_summary: str


def _skip_markup(text: str, index: int) -> int:
    """Return the index just past the `{{...}}` or `[[...]]` starting at `index`.

    Returns `index` unchanged when nothing opens there. Unclosed markup consumes
    the rest of the string rather than raising, so a malformed value degrades to
    a single field instead of losing the whole episode.
    """
    for opening, closing in (("{{", "}}"), ("[[", "]]")):
        if not text.startswith(opening, index):
            continue
        depth = 0
        position = index
        while position < len(text):
            if text.startswith(opening, position):
                depth += 1
                position += 2
            elif text.startswith(closing, position):
                depth -= 1
                position += 2
                if depth == 0:
                    return position
            else:
                position += 1
        return len(text)
    return index


def iter_template_bodies(wikitext: str, name: str) -> list[str]:
    """Return the inside of every `{{name|...}}` template, outermost first.

    Nested templates stay inside the returned body; they are not returned again
    on their own.
    """
    wanted = name.strip().casefold()
    bodies: list[str] = []
    position = 0
    while position < len(wikitext):
        if not wikitext.startswith("{{", position):
            position += 1
            continue
        end = _skip_markup(wikitext, position)
        body = wikitext[position + 2 : end - 2]
        head = _split_at_depth(body, "|")[0].strip().casefold()
        if head == wanted:
            bodies.append(body)
            position = end
        else:
            # Not the template we want, but a matching one may be nested inside.
            position += 2
    return bodies


def _split_at_depth(text: str, separator: str) -> list[str]:
    """Split on `separator` only where no template or link is open."""
    parts: list[str] = []
    start = 0
    position = 0
    while position < len(text):
        skipped = _skip_markup(text, position)
        if skipped != position:
            position = skipped
            continue
        if text.startswith(separator, position):
            parts.append(text[start:position])
            position += len(separator)
            start = position
            continue
        position += 1
    parts.append(text[start:])
    return parts


def template_fields(body: str) -> dict[str, str]:
    """Return the named fields of a template body, keyed exactly as written.

    Positional arguments are dropped; the episode templates only use them for the
    season page name, which the pipeline already knows.
    """
    fields: dict[str, str] = {}
    for part in _split_at_depth(body, "|")[1:]:
        head, separator, value = _partition_at_depth(part, "=")
        if separator:
            fields[head.strip()] = value.strip()
    return fields


def _partition_at_depth(text: str, separator: str) -> tuple[str, str, str]:
    position = 0
    while position < len(text):
        skipped = _skip_markup(text, position)
        if skipped != position:
            position = skipped
            continue
        if text.startswith(separator, position):
            return text[:position], separator, text[position + len(separator) :]
        position += 1
    return text, "", ""


def strip_references(value: str) -> str:
    """Remove reference tags and HTML comments, which are citations, not prose."""
    value = _HTML_COMMENT.sub("", value)
    value = _REF_PAIR.sub("", value)
    return _REF_SELF_CLOSING.sub("", value)


def _resolve_links(value: str) -> str:
    """Replace `[[target|label]]` with its label and `[[target]]` with its text."""
    out: list[str] = []
    position = 0
    while position < len(value):
        if value.startswith("[[", position):
            end = _skip_markup(value, position)
            inner = value[position + 2 : end - 2]
            parts = _split_at_depth(inner, "|")
            target = parts[0].strip()
            if target.casefold().startswith(("file:", "image:")):
                # Images carry captions full of unrelated markup; drop them whole.
                out.append("")
            elif len(parts) > 1:
                out.append(_resolve_links(parts[-1]).strip())
            else:
                out.append(target.split("#", 1)[0].strip())
            position = end
            continue
        out.append(value[position])
        position += 1
    return "".join(out)


def _drop_templates(value: str) -> str:
    """Remove any remaining templates.

    Templates that carry meaning, such as air dates and writing credits, are read
    before this runs. Whatever is left is presentation markup.
    """
    out: list[str] = []
    position = 0
    while position < len(value):
        if value.startswith("{{", position):
            position = _skip_markup(value, position)
            continue
        out.append(value[position])
        position += 1
    return "".join(out)


def clean_text(value: str) -> str:
    """Turn a wikitext fragment into the plain prose stored as episode content."""
    value = strip_references(value)
    value = _resolve_links(value)
    value = _drop_templates(value)
    value = _EXTERNAL_LINK.sub(lambda match: match.group(1) or "", value)
    value = _BOLD_ITALIC.sub("", value)
    value = _HTML_TAG.sub("", value)
    value = html.unescape(value)
    value = _SPACES.sub(" ", value)
    value = "\n".join(line.strip() for line in value.splitlines())
    return _BLANK_LINES.sub("\n\n", value).strip()


def parse_title_field(value: str) -> tuple[str, str | None]:
    """Return the displayed episode title and its standalone article, if linked."""
    stripped = strip_references(value).strip()
    if stripped.startswith("[[") and _skip_markup(stripped, 0) == len(stripped):
        inner = stripped[2:-2]
        parts = _split_at_depth(inner, "|")
        article = parts[0].split("#", 1)[0].strip()
        label = clean_text(parts[-1]) if len(parts) > 1 else article
        return label, article
    return clean_text(stripped), None


def parse_start_date(value: str) -> date | None:
    """Read `{{Start date|YYYY|M|D}}`, the only air-date form these pages use."""
    for body in iter_template_bodies(value, "Start date"):
        parts = [part.strip() for part in _split_at_depth(body, "|")[1:]]
        numbers = [part for part in parts if part.isdigit()]
        if len(numbers) >= 3:
            return date(int(numbers[0]), int(numbers[1]), int(numbers[2]))
    return None


def parse_credits(value: str) -> str:
    """Clean a DirectedBy or WrittenBy field, expanding split writing credits."""
    for body in iter_template_bodies(value, "StoryTeleplay"):
        fields = template_fields(body)
        story = clean_text(fields.get("s", ""))
        teleplay = clean_text(fields.get("t", ""))
        pieces = [
            piece
            for piece in (
                f"Story by {story}" if story else "",
                f"Teleplay by {teleplay}" if teleplay else "",
            )
            if piece
        ]
        if pieces:
            return "; ".join(pieces)
    return clean_text(value)


def parse_viewers(value: str) -> float | None:
    """Read the leading number of a Viewers field, ignoring its citations."""
    cleaned = clean_text(value)
    match = re.match(r"\d+(?:\.\d+)?", cleaned)
    return float(match.group()) if match else None


def parse_episode_list(wikitext: str) -> list[EpisodeListEntry]:
    """Parse every episode row in a season page's Episodes section."""
    entries: list[EpisodeListEntry] = []
    for body in iter_template_bodies(wikitext, EPISODE_TEMPLATE):
        fields = template_fields(body)
        season_number = fields.get("EpisodeNumber2", "").strip()
        if not season_number.isdigit():
            raise WikitextError(
                f"Episode row has no numeric EpisodeNumber2: {fields!r}"
            )

        title, article = parse_title_field(fields.get("Title", ""))
        if not title:
            raise WikitextError(f"Episode row {season_number} has no title.")

        summary = clean_text(fields.get("ShortSummary", ""))
        if not summary:
            raise WikitextError(
                f"Episode row {season_number} has an empty ShortSummary."
            )

        series_number = fields.get("EpisodeNumber", "").strip()
        entries.append(
            EpisodeListEntry(
                series_episode_number=int(series_number)
                if series_number.isdigit()
                else None,
                season_episode_number=int(season_number),
                title=title,
                standalone_article_title=article,
                directed_by=parse_credits(fields.get("DirectedBy", "")),
                written_by=parse_credits(fields.get("WrittenBy", "")),
                original_air_date=parse_start_date(fields.get("OriginalAirDate", "")),
                production_code=clean_text(fields.get("ProdCode", "")),
                us_viewers_millions=parse_viewers(fields.get("Viewers", "")),
                season_table_summary=summary,
            )
        )
    return entries


def parse_prose_section(wikitext: str, description: str) -> str:
    """Turn a section of an article into the plain prose stored as content.

    Headings are removed rather than kept, because a search unit built from this
    text should read as prose, not as a page outline. `description` only names
    the section in the error raised when nothing survives cleaning.
    """
    without_headings = _HEADING_LINE.sub("", wikitext)
    prose = clean_text(without_headings)
    if not prose:
        raise WikitextError(f"{description} section is empty after cleaning.")
    return prose
