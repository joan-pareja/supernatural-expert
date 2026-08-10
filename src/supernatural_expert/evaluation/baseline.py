"""Scores every retrieval setup the project can run, and compares them.

Run it from the repository root, after the index is built:

    uv run python -m supernatural_expert.evaluation

Only the tuning side is read. Once a setup has been chosen from those results,
`--held-out` scores that one setup over the questions no comparison has seen,
which is the whole point of having split it.

This is the run every retrieval decision rests on: which path ships, and whether
a stage added over it earns what it costs.

Two tables come out of it. Scores say how each setup did; differences say whether
it beat the simpler setup it was measured against, which is the question a choice
actually asks. See docs/evaluation.md.
"""

import csv
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from supernatural_expert.config import load_settings
from supernatural_expert.embedding.encoder import Encoder
from supernatural_expert.evaluation.dataset import (
    RESULTS_DIR,
    Question,
    load_held_out,
    load_questions,
    split,
)
from supernatural_expert.evaluation.retrieval import (
    HIT_RATE_RANKS,
    Difference,
    Score,
    compare,
    measure,
    score,
)
from supernatural_expert.reranking.models import (
    MS_MARCO_MINILM_L6_V2,
    MS_MARCO_MINILM_L12_V2,
    RerankerModel,
)
from supernatural_expert.reranking.reranker import Reranker
from supernatural_expert.search.engine import SearchEngine, SearchPath
from supernatural_expert.search.index import connect


@dataclass(frozen=True, slots=True)
class Setup:
    """One searchable configuration and the simpler one it must beat.

    `against` names that simpler setup, which is lexical for the paths and the
    unreranked path for a reranked one: each extra is judged against what it was
    added to, so a stage that cannot be told apart from the thing it wraps has
    not earned what it costs. The baseline itself has nothing below it.
    """

    label: str
    path: SearchPath
    rerank: bool = False
    against: str | None = "lexical"
    reranker: RerankerModel = MS_MARCO_MINILM_L6_V2


# Each cross-encoder is named here rather than taken from DEFAULT_RERANKER, so
# adopting a winner changes what the app ships without changing what this
# measured. A comparison that moved with the default could not be reproduced
# after it had decided anything.
SETUPS = (
    Setup("lexical", "lexical", against=None),
    Setup("vector", "vector"),
    Setup("hybrid", "hybrid"),
    Setup("hybrid+rerank", "hybrid", rerank=True, against="hybrid"),
    # The larger cross-encoder is judged against the smaller one rather than
    # against plain hybrid, because what is being asked is whether the extra
    # depth is worth its cost, not whether reranking works at all.
    Setup(
        "hybrid+rerank-L12",
        "hybrid",
        rerank=True,
        against="hybrid+rerank",
        reranker=MS_MARCO_MINILM_L12_V2,
    ),
)

# The setup the tuning side chose, and the only one the held-out side ever sees.
ADOPTED = "hybrid+rerank-L12"

SCORES_FILE = RESULTS_DIR / "retrieval_scores.csv"
DIFFERENCES_FILE = RESULTS_DIR / "retrieval_differences.csv"
HELD_OUT_FILE = RESULTS_DIR / "retrieval_held_out.csv"

SCORE_COLUMNS = (
    ["setup", "questions"]
    + [f"hit_rate_{at}" for at in HIT_RATE_RANKS]
    + ["mrr", "mrr_low", "mrr_high"]
)

DIFFERENCE_COLUMNS = [
    "setup",
    "against",
    "mean",
    "low",
    "high",
    "tie",
    "better",
    "worse",
    "tied",
]


def _decimal(value: float) -> str:
    return f"{value:.4f}"


def score_row(label: str, scored: Score) -> list[str]:
    """Render one scored setup for the table and the file alike."""
    return [
        label,
        str(scored.questions),
        *(_decimal(scored.hit_rates[at]) for at in HIT_RATE_RANKS),
        _decimal(scored.mrr),
        *(_decimal(bound) for bound in scored.interval),
    ]


def difference_row(setup: Setup, difference: Difference) -> list[str]:
    """Render one comparison, with the counts the mean was built from."""
    return [
        setup.label,
        str(setup.against),
        _decimal(difference.mean),
        *(_decimal(bound) for bound in difference.interval),
        "tie" if difference.tie else "decided",
        str(difference.better),
        str(difference.worse),
        str(difference.tied),
    ]


def render(columns: list[str], rows: list[list[str]]) -> str:
    """Draw one table as Markdown."""
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    lines.extend("| " + " | ".join(row) + " |" for row in rows)
    return "\n".join(lines)


def write_results(columns: list[str], rows: list[list[str]], path: Path) -> None:
    """Write one table where a later run can be compared against it."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, quoting=csv.QUOTE_ALL)
        writer.writerow(columns)
        writer.writerows(rows)


def run(connection: Any, questions: list[Question]) -> dict[str, list[int | None]]:
    """Measure every setup over the same questions, reporting each as it finishes.

    The measurements are returned rather than the scores, because comparing two
    setups needs their per-question ranks and a score has already averaged them
    away.

    One engine is built per cross-encoder, sharing the encoder between them: the
    embedding side is the same for every setup here, and loading those weights
    once keeps a comparison of rerankers from paying for it twice.
    """
    encoder = Encoder()
    engines: dict[str, SearchEngine] = {}
    measurements: dict[str, list[int | None]] = {}
    for setup in SETUPS:
        key = setup.reranker.repository if setup.rerank else "none"
        if key not in engines:
            engines[key] = SearchEngine(
                connection,
                encoder=encoder,
                reranker=Reranker(setup.reranker) if setup.rerank else None,
            )
        measurements[setup.label] = measure(
            engines[key], questions, path=setup.path, rerank=setup.rerank
        )
        print(f"  {setup.label}: MRR {score(measurements[setup.label]).mrr:.4f}")
    return measurements


def confirm(connection: Any, questions: list[Question]) -> int:
    """Score the adopted setup on the held-out side, and nothing else.

    One setup, once. Running the runner-up here too would turn these questions
    into a second tuning set, and the choice would have nothing left to be
    checked against. This answers whether the winner holds up, never which
    should have won.
    """
    setup = next(item for item in SETUPS if item.label == ADOPTED)
    ranks = measure(
        SearchEngine(connection, reranker=Reranker(setup.reranker)),
        questions,
        path=setup.path,
        rerank=setup.rerank,
    )
    row = score_row(setup.label, score(ranks))
    write_results(SCORE_COLUMNS, [row], HELD_OUT_FILE)
    print()
    print(render(SCORE_COLUMNS, [row]))
    print()
    print(f"Wrote {HELD_OUT_FILE}.")
    return 0


def main() -> int:
    settings = load_settings()
    questions = load_questions()
    tuning, held_out = split(questions, load_held_out())

    if "--held-out" in sys.argv[1:]:
        print(f"Reading {len(held_out)} held-out questions with {ADOPTED}.")
        connection = connect(settings)
        try:
            return confirm(connection, held_out)
        finally:
            connection.close()

    print(
        f"Scoring {len(tuning)} tuning questions. "
        f"{len(held_out)} held-out questions are not read here."
    )

    connection = connect(settings)
    try:
        measurements = run(connection, tuning)
    finally:
        connection.close()

    scores = [score_row(label, score(ranks)) for label, ranks in measurements.items()]
    differences = [
        difference_row(
            setup, compare(measurements[setup.label], measurements[setup.against])
        )
        for setup in SETUPS
        if setup.against is not None
    ]

    write_results(SCORE_COLUMNS, scores, SCORES_FILE)
    write_results(DIFFERENCE_COLUMNS, differences, DIFFERENCES_FILE)

    print()
    print(render(SCORE_COLUMNS, scores))
    print()
    print(render(DIFFERENCE_COLUMNS, differences))
    print()
    print(f"Wrote {SCORES_FILE} and {DIFFERENCES_FILE}.")
    return 0
