"""Scores the three retrieval paths before anything is tuned.

Run it from the repository root, after the index is built:

    uv run python -m supernatural_expert.evaluation

Only the tuning side is read. The held-out side stays unread until a setup has
been chosen, which is the whole point of having split it.

This is the run that decides whether tuning is worth doing. The corpus holds 132
documents, so a measure that is already near its ceiling here cannot separate a
tuned setup from an untuned one, and a search over it would be fitting noise.

Two tables come out of it. Scores say how each path did; differences say whether
any path beat the simplest one, which is the question a choice actually rests on.
See docs/evaluation.md.
"""

import csv
from pathlib import Path

from supernatural_expert.config import load_settings
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
from supernatural_expert.search.engine import SearchEngine, SearchPath
from supernatural_expert.search.index import connect

PATHS: tuple[SearchPath, ...] = ("lexical", "vector", "hybrid")

# What every other path is compared against. Lexical is the simplest of the
# three: one index, no encoder, no fusion. A path that cannot be told apart from
# it has not earned what it costs.
SIMPLEST_PATH: SearchPath = "lexical"

SCORES_FILE = RESULTS_DIR / "retrieval_scores.csv"
DIFFERENCES_FILE = RESULTS_DIR / "retrieval_differences.csv"

SCORE_COLUMNS = (
    ["path", "questions"]
    + [f"hit_rate_{at}" for at in HIT_RATE_RANKS]
    + ["mrr", "mrr_low", "mrr_high"]
)

DIFFERENCE_COLUMNS = [
    "path",
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


def score_row(path: SearchPath, scored: Score) -> list[str]:
    """Render one scored path for the table and the file alike."""
    return [
        path,
        str(scored.questions),
        *(_decimal(scored.hit_rates[at]) for at in HIT_RATE_RANKS),
        _decimal(scored.mrr),
        *(_decimal(bound) for bound in scored.interval),
    ]


def difference_row(path: SearchPath, difference: Difference) -> list[str]:
    """Render one comparison, with the counts the mean was built from."""
    return [
        path,
        SIMPLEST_PATH,
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


def run(
    engine: SearchEngine, questions: list[Question]
) -> dict[SearchPath, list[int | None]]:
    """Measure every path over the same questions, reporting each as it finishes.

    The measurements are returned rather than the scores, because comparing two
    paths needs their per-question ranks and a score has already averaged them
    away.
    """
    measurements: dict[SearchPath, list[int | None]] = {}
    for path in PATHS:
        measurements[path] = measure(engine, questions, path=path)
        print(f"  {path}: MRR {score(measurements[path]).mrr:.4f}")
    return measurements


def main() -> int:
    settings = load_settings()
    questions = load_questions()
    tuning, held_out = split(questions, load_held_out())
    print(
        f"Scoring {len(tuning)} tuning questions. "
        f"{len(held_out)} held-out questions are not read here."
    )

    connection = connect(settings)
    try:
        measurements = run(SearchEngine(connection), tuning)
    finally:
        connection.close()

    scores = [score_row(path, score(ranks)) for path, ranks in measurements.items()]
    differences = [
        difference_row(path, compare(ranks, measurements[SIMPLEST_PATH]))
        for path, ranks in measurements.items()
        if path != SIMPLEST_PATH
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
