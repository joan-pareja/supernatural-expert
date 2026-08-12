"""The ground truth questions and the split that keeps a chosen score honest.

Regenerate the split from the repository root, which overwrites the committed
file and invalidates every score measured against the old one:

    uv run python -m supernatural_expert.evaluation.dataset

The split is a list of documents rather than a list of questions. Questions about
one episode must never land on both sides, and choosing documents makes that
structural: a document sits on one side, and its questions follow it. See
docs/evaluation.md.
"""

import csv
import sys
from dataclasses import dataclass
from pathlib import Path
from random import Random
from typing import Iterable

from supernatural_expert.config import REPOSITORY_ROOT

EVALUATION_DIR = REPOSITORY_ROOT / "evaluation"
GROUND_TRUTH_FILE = EVALUATION_DIR / "ground_truth.csv"
HELD_OUT_FILE = EVALUATION_DIR / "held_out.csv"
ANSWER_SUBSET_A_FILE = EVALUATION_DIR / "answer_subset_a.csv"
ANSWER_SUBSET_B_FILE = EVALUATION_DIR / "answer_subset_b.csv"
RESULTS_DIR = EVALUATION_DIR / "results"

# A fifth of the documents. Large enough that the held-out score is not decided
# by a handful of questions, small enough that comparisons still see most of it.
HELD_OUT_FRACTION = 0.2

# Fixed so the split is reproducible from the questions alone, and the committed
# file can be checked rather than trusted.
HELD_OUT_SEED = 2026

# Questions each answer setup is judged over. Answer evaluation costs an answer
# and two judge calls per question per setup, so it reads a subset where
# retrieval scoring reads everything.
ANSWER_SUBSET_SIZE = 70
ANSWER_SUBSET_A_SEED = 2027

# A second sample of the same size, drawn from the tuning questions the first one
# left, so a setup can be read on questions no earlier answer run saw.
ANSWER_SUBSET_B_SEED = 2028


class GroundTruthError(RuntimeError):
    """Raised when an evaluation artifact is missing or unusable."""


@dataclass(frozen=True, slots=True)
class Question:
    """One ground truth question and the document that answers it."""

    document_id: str
    text: str


def is_season_introduction(document_id: str) -> bool:
    """Tell the two document kinds apart from the identifier alone.

    Identifiers are `sNN` for a season introduction and `sNNeNN` for an episode;
    ingestion owns that shape. Only six of the 132 documents are introductions,
    so a plain random split could leave all of them on one side.
    """
    return "e" not in document_id


def load_questions(path: Path = GROUND_TRUTH_FILE) -> list[Question]:
    """Read every ground truth question, in the order the file lists them."""
    if not path.is_file():
        raise GroundTruthError(f"{path} does not exist.")
    with path.open(encoding="utf-8", newline="") as handle:
        return [
            Question(document_id=row["document_id"], text=row["question"])
            for row in csv.DictReader(handle)
        ]


def choose_held_out(
    questions: list[Question],
    fraction: float = HELD_OUT_FRACTION,
    seed: int = HELD_OUT_SEED,
) -> list[str]:
    """Pick the documents whose questions are read once, at the end.

    Each kind is sampled separately, so the held-out side carries season
    introductions in the proportion the corpus does rather than by luck.
    """
    documents = sorted({question.document_id for question in questions})
    kinds = (
        [document for document in documents if is_season_introduction(document)],
        [document for document in documents if not is_season_introduction(document)],
    )
    generator = Random(seed)
    chosen: list[str] = []
    for kind in kinds:
        chosen.extend(generator.sample(kind, round(fraction * len(kind))))
    return sorted(chosen)


def choose_answer_subset(
    tuning: list[Question],
    size: int = ANSWER_SUBSET_SIZE,
    seed: int = ANSWER_SUBSET_A_SEED,
    exclude: Iterable[Question] = (),
) -> list[Question]:
    """Pick the questions an answer setup is read over.

    Drawn from the tuning side alone, so the held-out documents stay unread until
    the single final pass, and stratified by document kind for the reason the
    held-out split is: six season introductions are easy to miss entirely.

    Questions rather than documents. A setup is read on what it answered, and
    nothing carries between questions, so a document appearing twice cannot leak
    the way it would in a retrieval split.

    `exclude` removes questions an earlier sample already spent, which is what
    makes a second sample a fresh read rather than the same one again.
    """
    spent = set(exclude)
    pool = [question for question in tuning if question not in spent]
    if size > len(pool):
        raise GroundTruthError(
            f"Asked for {size} questions, but {len(pool)} are left to draw from."
        )
    kinds = (
        [q for q in pool if is_season_introduction(q.document_id)],
        [q for q in pool if not is_season_introduction(q.document_id)],
    )
    generator = Random(seed)
    chosen: list[Question] = []
    for kind in kinds:
        chosen.extend(generator.sample(kind, round(size * len(kind) / len(pool))))
    return sorted(chosen, key=lambda question: (question.document_id, question.text))


def write_answer_subset(
    questions: list[Question], path: Path = ANSWER_SUBSET_A_FILE
) -> None:
    """Write the judged subset in the shape the ground truth already uses."""
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, quoting=csv.QUOTE_ALL)
        writer.writerow(["document_id", "question"])
        writer.writerows(
            [question.document_id, question.text] for question in questions
        )


def load_answer_subset(path: Path = ANSWER_SUBSET_A_FILE) -> list[Question]:
    """Read a committed sample, so a rerun reads the questions the last one did."""
    if not path.is_file():
        raise GroundTruthError(
            f"{path} does not exist. "
            "Run: uv run python -m supernatural_expert.evaluation.dataset"
        )
    return load_questions(path)


def write_held_out(document_ids: list[str], path: Path = HELD_OUT_FILE) -> None:
    """Write the held-out documents, one per line under a header."""
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, quoting=csv.QUOTE_ALL)
        writer.writerow(["document_id"])
        writer.writerows([document_id] for document_id in document_ids)


def load_held_out(path: Path = HELD_OUT_FILE) -> set[str]:
    """Read the committed split."""
    if not path.is_file():
        raise GroundTruthError(
            f"{path} does not exist. "
            "Run: uv run python -m supernatural_expert.evaluation.dataset"
        )
    with path.open(encoding="utf-8", newline="") as handle:
        return {row["document_id"] for row in csv.DictReader(handle)}


def split(
    questions: list[Question], held_out_ids: set[str]
) -> tuple[list[Question], list[Question]]:
    """Return the tuning questions first, then the held-out questions."""
    tuning = [q for q in questions if q.document_id not in held_out_ids]
    held_out = [q for q in questions if q.document_id in held_out_ids]
    return tuning, held_out


def main() -> int:
    questions = load_questions()
    held_out_ids = choose_held_out(questions)
    write_held_out(held_out_ids, HELD_OUT_FILE)
    tuning, held_out = split(questions, set(held_out_ids))
    subset = choose_answer_subset(tuning)
    write_answer_subset(subset, ANSWER_SUBSET_A_FILE)
    second = choose_answer_subset(tuning, seed=ANSWER_SUBSET_B_SEED, exclude=subset)
    write_answer_subset(second, ANSWER_SUBSET_B_FILE)
    print(
        f"Held out {len(held_out_ids)} of "
        f"{len({q.document_id for q in questions})} documents "
        f"({len(held_out)} questions), leaving {len(tuning)} for tuning."
    )
    print(f"Wrote {HELD_OUT_FILE}.")
    print(f"Wrote {ANSWER_SUBSET_A_FILE} with {len(subset)} judged questions.")
    print(f"Wrote {ANSWER_SUBSET_B_FILE} with {len(second)} judged questions.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
