"""Scores one retrieval setup against the ground truth.

Every question carries the document that answers it, so a search is right when
that document appears and how right depends on where. Scoring is therefore rank
arithmetic and nothing else: no model runs here, and the same questions over the
same index reproduce a number rather than approximate it.

Measuring and scoring are separate steps. Ranks are the expensive part and the
metrics are pure arithmetic over them, so one measurement answers every question
asked of it and two setups can be compared question by question afterwards.

A score says how one setup did. `compare` says whether one setup beat another,
which is a different question and the one every choice here rests on. See
docs/evaluation.md.
"""

from dataclasses import dataclass
from math import ceil, floor
from random import Random
from statistics import mean
from typing import Sequence

from supernatural_expert.evaluation.dataset import Question
from supernatural_expert.search.engine import (
    DEFAULT_CANDIDATES,
    DEFAULT_LIMIT,
    SearchEngine,
    SearchPath,
    SearchResult,
)

# The ranks reported beside MRR. One is where the corpus still separates setups;
# five is there to show when it has stopped doing so.
HIT_RATE_RANKS = (1, 5)

# Resamples behind the confidence interval. A thousand is enough to place an
# interval at this width and costs milliseconds, because it resamples the
# reciprocal ranks rather than rerunning any search.
BOOTSTRAP_SAMPLES = 1000
BOOTSTRAP_SEED = 2026
CONFIDENCE = 0.95


@dataclass(frozen=True, slots=True)
class Score:
    """What one setup achieved over one set of questions.

    The interval covers MRR alone and describes this score by itself: how much of
    it is the questions that happened to be asked. It does not decide anything
    between two setups; `compare` does that, and two intervals that overlap can
    still cover a real difference.
    """

    questions: int
    hit_rates: dict[int, float]
    mrr: float
    interval: tuple[float, float]


@dataclass(frozen=True, slots=True)
class Difference:
    """How much better one setup ranked than another, over the same questions.

    `mean` is positive when the setup beat the one it was compared against. The
    counts say how the difference arose: a gap resting on a handful of questions
    is a different thing from the same gap spread across all of them.
    """

    mean: float
    interval: tuple[float, float]
    better: int
    worse: int
    tied: int

    @property
    def tie(self) -> bool:
        """Whether the interval still admits the two setups being equal.

        A tie is not a claim that the setups are the same. It says this
        measurement cannot tell them apart, which is the point at which the
        simpler setup wins by default rather than on merit.
        """
        low, high = self.interval
        return low <= 0.0 <= high


def rank_of(results: Sequence[SearchResult], document_id: str) -> int | None:
    """Return the one-based position of the answering document, or None.

    None means the document was not in the results at all, which is different
    from being last in them. Every metric here treats it as a zero.
    """
    for position, result in enumerate(results, start=1):
        if result.document_id == document_id:
            return position
    return None


def measure(
    engine: SearchEngine,
    questions: Sequence[Question],
    path: SearchPath = "hybrid",
    limit: int = DEFAULT_LIMIT,
    candidates: int = DEFAULT_CANDIDATES,
    rerank: bool = False,
) -> list[int | None]:
    """Search once per question and return where each answering document landed.

    Ranks are kept per question rather than averaged here, because a confidence
    interval needs the individual results and an average has already lost them.
    """
    return [
        rank_of(
            engine.search(
                question.text,
                path=path,
                limit=limit,
                candidates=candidates,
                rerank=rerank,
            ),
            question.document_id,
        )
        for question in questions
    ]


def reciprocal_ranks(ranks: Sequence[int | None]) -> list[float]:
    """Turn ranks into the per-question values MRR averages."""
    return [0.0 if rank is None else 1 / rank for rank in ranks]


def hit_rate(ranks: Sequence[int | None], at: int) -> float:
    """Return the share of questions whose document reached the top `at`."""
    return mean(1.0 if rank is not None and rank <= at else 0.0 for rank in ranks)


def interval(
    values: Sequence[float],
    samples: int = BOOTSTRAP_SAMPLES,
    seed: int = BOOTSTRAP_SEED,
    confidence: float = CONFIDENCE,
) -> tuple[float, float]:
    """Bootstrap a percentile interval for the mean of `values`.

    A score is an average over the questions that happened to be asked, so a
    different set of questions would have produced a different one. The interval
    says how much different, which is what stops a small lead being read as a win.

    Another set cannot be collected, so one is imitated from this one: draw as
    many questions as there are, with replacement, so some appear twice and some
    not at all, and average those. A thousand such averages, sorted, with the
    outer 2.5% cut from each end, leave the middle 95%.

    The seed is fixed so two setups are compared through the same resampling.
    """
    generator = Random(seed)
    means = sorted(
        mean(generator.choices(values, k=len(values))) for _ in range(samples)
    )
    tail = (1 - confidence) / 2
    return means[floor(tail * samples)], means[ceil((1 - tail) * samples) - 1]


def score(
    ranks: Sequence[int | None],
    samples: int = BOOTSTRAP_SAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> Score:
    """Turn one measurement into the numbers a comparison is read from."""
    if not ranks:
        raise ValueError("Scoring needs at least one question.")
    values = reciprocal_ranks(ranks)
    return Score(
        questions=len(ranks),
        hit_rates={at: hit_rate(ranks, at) for at in HIT_RATE_RANKS},
        mrr=mean(values),
        interval=interval(values, samples=samples, seed=seed),
    )


def compare(
    candidate: Sequence[int | None],
    baseline: Sequence[int | None],
    samples: int = BOOTSTRAP_SAMPLES,
    seed: int = BOOTSTRAP_SEED,
) -> Difference:
    """Say whether `candidate` beat `baseline`, from two measurements of one set.

    Both setups answered the same questions in the same order, so each question
    yields a pair and the comparison is over the differences between them. That
    pairing is the whole reason this is sharper than reading two scores side by
    side: a question hard for one setup is usually hard for both, and subtracting
    removes that shared difficulty instead of measuring it twice.

    Two separate intervals can therefore overlap while the difference between the
    setups is real, which is why an overlap is not evidence of a tie and this is.
    """
    if not candidate:
        raise ValueError("Comparing needs at least one question.")
    if len(candidate) != len(baseline):
        raise ValueError(
            f"Comparing needs one measurement per question on both sides, "
            f"got {len(candidate)} and {len(baseline)}."
        )
    differences = [
        theirs - ours
        for theirs, ours in zip(reciprocal_ranks(candidate), reciprocal_ranks(baseline))
    ]
    return Difference(
        mean=mean(differences),
        interval=interval(differences, samples=samples, seed=seed),
        better=sum(1 for value in differences if value > 0),
        worse=sum(1 for value in differences if value < 0),
        tied=sum(1 for value in differences if value == 0),
    )
