"""Tests for the evaluation harness, over the committed artifacts and a stub engine.

No database is read and no model is called. What these pin is the arithmetic and
the split discipline: a document never appears on both sides, a rank becomes the
score it should, and a missing document counts as a zero rather than as a poor
position.
"""

from typing import cast

import pytest
from pydantic_ai.models.test import TestModel

from supernatural_expert.evaluation.answers import (
    MEASURES,
    Judged,
    build_dataset,
    verdict_rows,
    verdicts,
)
from supernatural_expert.evaluation.dataset import (
    ANSWER_SUBSET_B_FILE,
    ANSWER_SUBSET_B_SEED,
    ANSWER_SUBSET_SIZE,
    Question,
    choose_answer_subset,
    choose_held_out,
    is_season_introduction,
    load_answer_subset,
    load_held_out,
    load_questions,
    split,
)
from supernatural_expert.evaluation.retrieval import (
    compare,
    compare_values,
    hit_rate,
    measure,
    rank_of,
    reciprocal_ranks,
    score,
)
from supernatural_expert.search.engine import SearchEngine, SearchFilters, SearchResult

EXPECTED_DOCUMENTS = 132


def result(document_id: str) -> SearchResult:
    return SearchResult(
        document_id=document_id,
        title=document_id,
        season_number=1,
        episode_number=1,
        content="A hunter salts and burns the bones.",
        source_url=f"https://en.wikipedia.org/wiki/{document_id}",
        score=1.0,
        matched_text="salts and burns",
    )


class StubEngine:
    """A search engine that returns a fixed ranking for every question."""

    def __init__(self, results: list[SearchResult]) -> None:
        self.results = results
        self.calls: list[tuple[str, str, int, int, bool]] = []

    def search(
        self,
        query: str,
        path: str = "hybrid",
        limit: int = 10,
        filters: SearchFilters | None = None,
        candidates: int = 50,
        rerank: bool = False,
    ) -> list[SearchResult]:
        self.calls.append((query, path, limit, candidates, rerank))
        return self.results


def engine_for(*document_ids: str) -> StubEngine:
    return StubEngine([result(document_id) for document_id in document_ids])


def test_ground_truth_covers_every_document() -> None:
    questions = load_questions()
    assert len({question.document_id for question in questions}) == EXPECTED_DOCUMENTS


def test_committed_split_matches_the_seed() -> None:
    """The committed file is reproducible from the questions, so it can be checked."""
    assert load_held_out() == set(choose_held_out(load_questions()))


def test_split_puts_every_document_on_one_side() -> None:
    questions = load_questions()
    tuning, held_out = split(questions, load_held_out())

    assert len(tuning) + len(held_out) == len(questions)
    tuning_documents = {question.document_id for question in tuning}
    held_out_documents = {question.document_id for question in held_out}
    assert not tuning_documents & held_out_documents


def test_split_holds_out_both_document_kinds() -> None:
    held_out = load_held_out()
    assert any(is_season_introduction(document) for document in held_out)
    assert any(not is_season_introduction(document) for document in held_out)


def test_committed_answer_subset_matches_the_seed() -> None:
    """Both answer setups have to see the same questions in the same order."""
    tuning, _ = split(load_questions(), load_held_out())
    assert load_answer_subset() == choose_answer_subset(tuning)


def test_the_answer_subset_leaves_the_held_out_documents_unread() -> None:
    subset = load_answer_subset()
    assert len(subset) == ANSWER_SUBSET_SIZE
    assert not {question.document_id for question in subset} & load_held_out()


def test_the_second_answer_subset_is_a_fresh_sample() -> None:
    """A second read is only fresh if it shares no question with the first."""
    tuning, _ = split(load_questions(), load_held_out())
    first = load_answer_subset()
    second = load_answer_subset(ANSWER_SUBSET_B_FILE)

    assert second == choose_answer_subset(
        tuning, seed=ANSWER_SUBSET_B_SEED, exclude=first
    )
    assert len(second) == ANSWER_SUBSET_SIZE
    assert not set(first) & set(second)
    assert not {question.document_id for question in second} & load_held_out()


def test_comparing_values_pairs_them_question_by_question() -> None:
    """Two setups that swap wins on every question tie, however far apart each is."""
    decided = compare_values([1.0] * 20, [0.0] * 20)
    swapped = compare_values([1.0, 0.0] * 10, [0.0, 1.0] * 10)

    assert decided.mean == 1.0
    assert not decided.tie
    assert swapped.mean == 0.0
    assert swapped.tie


def test_the_report_names_every_measure_the_comparison_reads() -> None:
    """A renamed verdict would read as zero everywhere rather than as an error.

    The judge is a stub, so what this pins is the wiring between the evaluators
    and the names `verdicts` looks up, not anything about the answers.
    """
    questions = [Question(document_id="s01e05", text="Who dies in Toledo?")]
    dataset = build_dataset(questions, TestModel())

    def task(question: str) -> Judged:
        return Judged(
            text="A plumber.",
            citations=["s01e05"],
            cited_documents="The plumber drowns.",
            retrieved=["s01e05"],
        )

    report = dataset.evaluate_sync(task, progress=False, max_concurrency=1)

    assert sorted(report.cases[0].assertions) == sorted(MEASURES)
    assert verdicts(report, ["000-s01e05"], "retrieved") == [1.0]


def test_every_measure_is_written_out_with_its_verdict() -> None:
    """The reasons are the artifact; a measure missing here cannot be reviewed."""
    questions = [Question(document_id="s01e05", text="Who dies in Toledo?")]
    dataset = build_dataset(questions, TestModel())

    def task(question: str) -> Judged:
        return Judged(
            text="A plumber.",
            citations=["s01e05"],
            cited_documents="The plumber drowns.",
            retrieved=["s01e05"],
        )

    report = dataset.evaluate_sync(task, progress=False, max_concurrency=1)
    rows = verdict_rows(report, questions, ["000-s01e05"])

    assert [row[1] for row in rows] == list(MEASURES)
    assert all(row[0] == "Who dies in Toledo?" for row in rows)
    assert all(row[2] in {"pass", "fail"} for row in rows)


def test_a_question_whose_case_never_finished_still_gets_its_rows() -> None:
    """A question absent from the file would read as one that was never asked."""
    questions = [Question(document_id="s01e05", text="Who dies in Toledo?")]
    dataset = build_dataset(questions, TestModel())

    def task(question: str) -> Judged:
        return Judged(text="", citations=[], cited_documents="", retrieved=[])

    report = dataset.evaluate_sync(task, progress=False, max_concurrency=1)
    rows = verdict_rows(report, questions, ["no-such-case"])

    assert len(rows) == len(MEASURES)
    assert all(row[2] == "" for row in rows)


def test_rank_of_finds_the_answering_document() -> None:
    results = [result("s01e01"), result("s01e02"), result("s01e03")]
    assert rank_of(results, "s01e02") == 2
    assert rank_of(results, "s06e22") is None


def test_a_missing_document_scores_zero() -> None:
    """A document the search never returned counts as nothing, not as last."""
    assert reciprocal_ranks([1, 2, None]) == [1.0, 0.5, 0.0]
    assert hit_rate([1, 2, None], at=5) == 2 / 3


def test_hit_rate_counts_only_the_ranks_it_is_asked_about() -> None:
    assert hit_rate([1, 2, None], at=1) == 1 / 3


def test_measure_asks_the_engine_for_each_question() -> None:
    engine = engine_for("s01e02", "s01e01")
    questions = [Question("s01e01", "Who is Jessica?"), Question("s06e22", "Who wins?")]

    ranks = measure(
        cast(SearchEngine, engine), questions, path="lexical", limit=5, candidates=20
    )

    assert ranks == [2, None]
    assert engine.calls == [
        ("Who is Jessica?", "lexical", 5, 20, False),
        ("Who wins?", "lexical", 5, 20, False),
    ]


def test_compare_is_positive_when_the_candidate_ranks_better() -> None:
    """The sign says which side won, so it has to follow the argument order."""
    better = compare([1, 1, 2], [2, 2, 2])
    worse = compare([2, 2, 2], [1, 1, 2])

    assert better.mean > 0
    assert worse.mean == -better.mean


def test_compare_counts_how_the_difference_arose() -> None:
    difference = compare([1, 3, 2, None], [2, 1, 2, None])

    assert (difference.better, difference.worse, difference.tied) == (1, 1, 2)


def test_a_consistent_win_is_not_a_tie() -> None:
    """Every question improving leaves no resample in which the setups are equal."""
    difference = compare([1] * 20, [3] * 20)

    assert not difference.tie
    assert difference.interval[0] > 0


def test_setups_that_trade_questions_are_a_tie() -> None:
    """Wins and losses that cancel are a measurement that cannot separate them."""
    difference = compare([1, 3] * 10, [3, 1] * 10)

    assert difference.tie
    assert (difference.better, difference.worse) == (10, 10)


def test_comparing_needs_the_same_questions_on_both_sides() -> None:
    with pytest.raises(ValueError):
        compare([1, 2], [1])


def test_score_reports_every_metric() -> None:
    scored = score([1, 1, 2, None])

    assert scored.questions == 4
    assert scored.hit_rates == {1: 0.5, 5: 0.75}
    assert scored.mrr == 0.625
    low, high = scored.interval
    assert low <= scored.mrr <= high
