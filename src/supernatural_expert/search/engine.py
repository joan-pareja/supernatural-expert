"""The three search paths, over the units the indexer wrote.

Matching happens on a chunk; answering happens on a document. Every path
therefore ranks units, then collapses them so a document appears once, keeping
the position its best unit earned. Callers receive whole documents, because a
piece is enough to find an episode and not enough to describe one. See
docs/retrieval.md.

Lexical and vector search read the same units so that reciprocal rank fusion can
compare their positions. Fusion combines ranks and never reads the query again,
which is what separates it from reranking.
"""

from dataclasses import dataclass, field
from typing import Any, Literal

from supernatural_expert.embedding.encoder import Encoder
from supernatural_expert.ingestion.documents import DocumentType
from supernatural_expert.search.index import SCHEMA, UNIT_TABLE, to_pgvector

SearchPath = Literal["lexical", "vector", "hybrid"]

DEFAULT_LIMIT = 10

# Units each path retrieves before fusion. Deeper than the limit on purpose: a
# document one path ranks poorly can still win if the other ranks it well, and
# fusion can only see what both lists contain.
DEFAULT_CANDIDATES = 50

# The constant in 1 / (k + rank), from the paper that introduced the method. It
# flattens the gap between the top few positions so one path cannot dominate the
# other on a single confident hit. 60 is the published default and is kept rather
# than tuned.
RRF_K = 60

# Everything a result needs, in the order the row is unpacked.
RESULT_COLUMNS = (
    "unit_id",
    "document_id",
    "title",
    "season_number",
    "episode_number",
    "content",
    "source_url",
    "unit_text",
)


@dataclass(frozen=True, slots=True)
class SearchFilters:
    """Narrowing a caller may ask for. Every field left None means no filter.

    These narrow a search and do nothing else. None of them enforces a rule, so a
    caller that sets one wrongly gets fewer results rather than results it should
    not have been shown.
    """

    season: int | None = None
    episode: int | None = None
    document_type: DocumentType | None = None

    def where(self) -> tuple[str, dict[str, Any]]:
        """Return the filter conditions and the values they name, empty if unset.

        The conditions are joined here because they always combine the same way.
        The fragment does not begin with a conjunction, so it stands on its own
        and a caller attaches it to whatever predicates its own path already has.

        Each value is named rather than positional, so a caller merges it into
        its own parameters and the order it writes them in cannot matter.
        """
        conditions: list[str] = []
        values: dict[str, Any] = {}
        for name, column, value in (
            ("season", "season_number", self.season),
            ("episode", "episode_number", self.episode),
            ("document_type", "document_type", self.document_type),
        ):
            if value is not None:
                conditions.append(f"{column} = %({name})s")
                values[name] = value
        return " AND ".join(conditions), values


@dataclass(frozen=True, slots=True)
class SearchResult:
    """One document a search found, with the piece that found it.

    `content` is the whole document and is what an answer is written from.
    `matched_text` is the unit that earned the position, kept for inspecting why
    a result appeared rather than for answering.

    `score` orders results within one query on one path. It is not comparable
    across queries or across paths: lexical scores are BM25 values, vector
    scores are cosine similarities, and hybrid scores are fused ranks.
    """

    document_id: str
    title: str
    season_number: int
    episode_number: int | None
    content: str
    source_url: str
    score: float
    matched_text: str


@dataclass(frozen=True, slots=True)
class _Candidate:
    """One ranked unit, before documents are deduplicated."""

    unit_id: str
    document_id: str
    title: str
    season_number: int
    episode_number: int | None
    content: str
    source_url: str
    unit_text: str
    score: float = field(default=0.0, compare=False)


class SearchEngine:
    """Runs every search path against one index.

    The connection and encoder are held rather than created per call, because
    loading an encoder's weights costs far more than running a search does.
    Instances are not thread-safe, because the encoder is not.
    """

    def __init__(self, connection: Any, encoder: Encoder | None = None) -> None:
        self._connection = connection
        # Built on first vector search rather than here, so a lexical-only
        # session never pays for weights it does not use.
        self._encoder = encoder

    @property
    def encoder(self) -> Encoder:
        if self._encoder is None:
            self._encoder = Encoder()
        return self._encoder

    def search(
        self,
        query: str,
        path: SearchPath = "hybrid",
        limit: int = DEFAULT_LIMIT,
        filters: SearchFilters | None = None,
        candidates: int = DEFAULT_CANDIDATES,
    ) -> list[SearchResult]:
        """Return the best documents for `query`, best first.

        One entry point for every path, so choosing between them is an argument
        rather than a different call.
        """
        filters = filters or SearchFilters()
        if path == "lexical":
            ranked = self._search_lexical(query, filters, candidates)
        elif path == "vector":
            ranked = self._search_vector(query, filters, candidates)
        else:
            ranked = self._fuse(
                self._search_lexical(query, filters, candidates),
                self._search_vector(query, filters, candidates),
            )
        return self._collapse(ranked, limit)

    def _search_lexical(
        self, query: str, filters: SearchFilters, candidates: int
    ) -> list[_Candidate]:
        """Rank units by BM25 over the title and the piece.

        `|||` matches disjunctively: a unit is a candidate if it carries any of
        the question's terms, and BM25 then scores it on how many it carries and
        how rare each one is. Rarity is the part that matters here. In "What do
        Dean and Bobby find left of the Roadhouse?", `dean` occurs in almost every
        unit and identifies nothing, while `roadhous` occurs in a handful and
        identifies the episode; BM25 weights them accordingly.

        Terms are stemmed and stop words dropped on both sides, so "brothers" in
        a question meets "brother" in a plot.
        """
        conditions, filter_values = filters.where()
        # Either field may carry the match, and then whatever the caller asked
        # for narrows it.
        where = "(title ||| %(query)s OR unit_text ||| %(query)s)"
        if conditions:
            where += f" AND {conditions}"
        sql = f"""
            SELECT
                {", ".join(RESULT_COLUMNS)},
                pdb.score(unit_id) AS score
            FROM {SCHEMA}.{UNIT_TABLE}
            WHERE {where}
            ORDER BY score DESC, unit_id
            LIMIT %(candidates)s
        """
        return self._fetch(
            sql, {"query": query, "candidates": candidates, **filter_values}
        )

    def _search_vector(
        self, query: str, filters: SearchFilters, candidates: int
    ) -> list[_Candidate]:
        """Rank units by cosine similarity to the encoded query.

        The query is encoded through `encode_query`, which applies the model's
        query marker. Encoding it as a passage instead would compare two
        different kinds of text and quietly lose accuracy.
        """
        conditions, filter_values = filters.where()
        # Every unit is a candidate here, so an unfiltered search has no WHERE
        # clause at all rather than a placeholder condition.
        where = f"WHERE {conditions}" if conditions else ""
        # Vectors are unit length, so cosine distance subtracted from one is the
        # cosine similarity. The scan is exact; see docs/data-model.md.
        sql = f"""
            SELECT
                {", ".join(RESULT_COLUMNS)},
                1 - (embedding <=> %(vector)s::vector) AS score
            FROM {SCHEMA}.{UNIT_TABLE}
            {where}
            ORDER BY embedding <=> %(vector)s::vector, unit_id
            LIMIT %(candidates)s
        """
        return self._fetch(
            sql,
            {
                "vector": to_pgvector(self.encoder.encode_query(query)),
                "candidates": candidates,
                **filter_values,
            },
        )

    def _fetch(self, sql: str, params: dict[str, Any]) -> list[_Candidate]:
        """Run one ranking query and return its rows as candidates.

        Every path selects RESULT_COLUMNS and then a score, so a row is those
        columns by name followed by the score. Building each candidate from the
        column names means the two orders do not have to agree.
        """
        with self._connection.cursor() as cursor:
            cursor.execute(sql, params)
            rows = cursor.fetchall()
        return [
            _Candidate(
                **dict(zip(RESULT_COLUMNS, row)),  # pyright: ignore[reportAny]
                score=float(row[-1]),  # pyright: ignore[reportAny]
            )
            for row in rows
        ]

    @staticmethod
    def _fuse(*rankings: list[_Candidate]) -> list[_Candidate]:
        """Combine ranked lists with reciprocal rank fusion.

        Only positions are used, never the underlying scores, because a BM25
        value and a cosine similarity are on unrelated scales and adding them
        would let whichever happens to be larger decide the order.
        """
        scores: dict[str, float] = {}
        units: dict[str, _Candidate] = {}
        for ranking in rankings:
            for position, candidate in enumerate(ranking, start=1):
                scores[candidate.unit_id] = scores.get(candidate.unit_id, 0.0) + 1 / (
                    RRF_K + position
                )
                units.setdefault(candidate.unit_id, candidate)

        return [
            _Candidate(
                unit_id=unit_id,
                document_id=units[unit_id].document_id,
                title=units[unit_id].title,
                season_number=units[unit_id].season_number,
                episode_number=units[unit_id].episode_number,
                content=units[unit_id].content,
                source_url=units[unit_id].source_url,
                unit_text=units[unit_id].unit_text,
                score=score,
            )
            for unit_id, score in sorted(
                scores.items(), key=lambda item: (-item[1], item[0])
            )
        ]

    @staticmethod
    def _collapse(ranked: list[_Candidate], limit: int) -> list[SearchResult]:
        """Keep each document once, at the position its best unit reached.

        A document long enough to split would otherwise fill the results with
        itself, crowding out documents its best piece only narrowly beat. Every
        document therefore competes as one result however many units it holds.
        """
        results: list[SearchResult] = []
        seen: set[str] = set()
        for candidate in ranked:
            if candidate.document_id in seen:
                continue
            seen.add(candidate.document_id)
            results.append(
                SearchResult(
                    document_id=candidate.document_id,
                    title=candidate.title,
                    season_number=candidate.season_number,
                    episode_number=candidate.episode_number,
                    content=candidate.content,
                    source_url=candidate.source_url,
                    score=candidate.score,
                    matched_text=candidate.unit_text,
                )
            )
            if len(results) == limit:
                break
        return results
