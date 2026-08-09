"""Tests for the reranking stage, over a stub index and a stub cross-encoder.

No database is read and no model is called. What these pin is the contract around
the shortlist: the head comes back in the order the scores asked for, the tail
below it is left alone, and a reranked search still returns as many documents as
an unreranked one.
"""

from typing import Any, cast

from supernatural_expert.reranking.reranker import Reranker
from supernatural_expert.search.engine import (
    RERANK_DEPTH,
    RESULT_COLUMNS,
    SearchEngine,
)


class StubCursor:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self.rows = rows

    def __enter__(self) -> "StubCursor":
        return self

    def __exit__(self, *_: object) -> bool:
        return False

    def execute(self, sql: str, params: dict[str, Any]) -> None:
        pass

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self.rows


class StubConnection:
    """An index that answers every query with the same ranked rows."""

    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self.rows = rows

    def cursor(self) -> StubCursor:
        return StubCursor(self.rows)


class StubReranker:
    """Scores passages by a lookup, so a test states the order it wants."""

    def __init__(self, scores: dict[str, float]) -> None:
        self.scores = scores
        self.seen: list[str] = []

    def score(self, query: str, passages: list[str]) -> list[float]:
        self.seen = passages
        return [self.scores.get(passage, 0.0) for passage in passages]


def row(document_id: str, score: float) -> tuple[Any, ...]:
    """One index row, in the order every path selects it."""
    values: dict[str, Any] = {
        "unit_id": f"{document_id}-0",
        "document_id": document_id,
        "title": document_id,
        "season_number": 1,
        "episode_number": 1,
        "content": f"The whole of {document_id}.",
        "source_url": f"https://en.wikipedia.org/wiki/{document_id}",
        "unit_text": f"A piece of {document_id}.",
    }
    return (*(values[column] for column in RESULT_COLUMNS), score)


def engine_over(document_ids: list[str], reranker: StubReranker) -> SearchEngine:
    rows = [
        row(document_id, 1.0 - index) for index, document_id in enumerate(document_ids)
    ]
    return SearchEngine(StubConnection(rows), reranker=cast(Reranker, reranker))


def test_reranking_reorders_the_shortlist() -> None:
    reranker = StubReranker({"A piece of s01e03.": 9.0})
    engine = engine_over(["s01e01", "s01e02", "s01e03"], reranker)

    results = engine.search("a question", path="lexical", rerank=True)

    assert [result.document_id for result in results] == ["s01e03", "s01e01", "s01e02"]


def test_the_cross_encoder_reads_the_piece_and_not_the_document() -> None:
    """A document is far longer than the pair window, so the unit is what it sees."""
    reranker = StubReranker({})
    engine = engine_over(["s01e01"], reranker)

    engine.search("a question", path="lexical", rerank=True)

    assert reranker.seen == ["A piece of s01e01."]


def test_a_reranked_search_still_fills_the_limit() -> None:
    """The unscored tail stays below the shortlist rather than being dropped."""
    documents = [f"s01e{index:02d}" for index in range(1, RERANK_DEPTH + 6)]
    engine = engine_over(documents, StubReranker({}))

    results = engine.search("a question", path="lexical", rerank=True, limit=10)

    assert len(results) == 10


def test_the_tail_keeps_the_order_the_first_stage_gave_it() -> None:
    documents = [f"s01e{index:02d}" for index in range(1, RERANK_DEPTH + 4)]
    engine = engine_over(documents, StubReranker({}))

    results = engine.search(
        "a question", path="lexical", rerank=True, limit=len(documents)
    )

    assert [result.document_id for result in results[RERANK_DEPTH:]] == (
        documents[RERANK_DEPTH:]
    )
