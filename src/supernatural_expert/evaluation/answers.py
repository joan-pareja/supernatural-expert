"""Judging whole answers: how well the adopted setup answers, on its own terms.

Run it from the repository root, with a database already loaded:

    uv run python -m supernatural_expert.evaluation.answers

This is the only measurement in the project that spends money and does not
reproduce exactly, which is why it has an entry point of its own rather than
running beside the retrieval scores. Each question costs one agent run and two
judge calls, so it reads a committed subset where retrieval scoring reads every
question. See docs/evaluation.md.

It is also the only measurement that runs the whole loop. A retrieval score
searches one question and stops; here the question is searched verbatim, the
agent rewrites and searches again if it needs to, and it is read on what it
finally said.
"""

import csv
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Annotated, Callable, Mapping, Sequence

from pydantic import Field
from pydantic_ai import Agent
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_evals import Case, Dataset, increment_eval_metric
from pydantic_evals.evaluators import (
    EvaluationReason,
    Evaluator,
    EvaluatorContext,
)
from pydantic_evals.reporting import EvaluationReport

from supernatural_expert.agent.answering import (
    ANSWER_DOCUMENTS,
    AnswerDeps,
    ask,
    build_model,
)
from supernatural_expert.config import Settings, load_settings
from supernatural_expert.evaluation.dataset import (
    ANSWER_SUBSET_B_FILE,
    RESULTS_DIR,
    Question,
    load_answer_subset,
    load_held_out,
    load_questions,
    split,
)
from supernatural_expert.monitoring.telemetry import configure_telemetry
from supernatural_expert.search.engine import SearchEngine
from supernatural_expert.search.index import connect

SCORES_FILE = RESULTS_DIR / "answer_scores.csv"

# One row per question and measure, carrying the judge's own justification. The
# scores say how many answers failed; only this says what they got wrong, and
# reading a dozen of these is what turns a dropped measure into a change worth
# making.
VERDICTS_FILE = RESULTS_DIR / "answer_verdicts.csv"

# `--held-out` reads the questions no tuning run has seen, once, with the setup
# already chosen. It writes its own files so a held-out score can never overwrite
# the tuning one it is meant to be compared against.
HELD_OUT_SCORES_FILE = RESULTS_DIR / "answer_held_out.csv"
HELD_OUT_VERDICTS_FILE = RESULTS_DIR / "answer_held_out_verdicts.csv"

# The questions this reads. The second sample rather than the first, so the
# adopted setup is scored on questions no earlier answer run saw.
SUBSET_FILE = ANSWER_SUBSET_B_FILE

# Pinned, and stated here rather than taken from the answering model, because a
# judge that moves makes two runs incomparable for a reason that has nothing to
# do with the setups. It is deliberately not the answering model: a judge cannot
# be trusted to catch a mistake it would have made itself.
JUDGE_MODEL = "gpt-5.6-terra"

JUDGE_INSTRUCTIONS = """
You grade one answer against one rubric and nothing else.

The answer was written for a viewer watching Supernatural, from documents a
search returned. You are shown the question, the answer, and the documents the
answer cited.

Judge only what the rubric asks. An answer can be well written and still fail,
and a blunt one can pass.

Judge against the documents shown rather than against what you know about the
series. What you remember of Supernatural is not evidence here.

Give a verdict and one or two sentences saying why. State the justification
only; do not narrate your reasoning or correct yourself in it.
"""

RELEVANCE_RUBRIC = """
The answer addresses the question that was asked. An answer that says the corpus
does not cover the question passes only if the cited documents genuinely do not
hold it; an answer that refuses a question the documents do answer fails.
"""

SUPPORT_RUBRIC = """
Every factual claim about the series in the answer appears in the cited
documents shown with it. Claims that are plausibly true of Supernatural but
absent from those documents fail this rubric.

Judge only what the answer adds. An answer restates the question's own premise
to read naturally, and repeating back what the asker already supplied is not a
claim it is making. A question asking how a man died after his daughter played
the mirror game may be answered "he died after his daughter played the mirror
game, when his eyes burst", and only the eyes have to be in the documents.
"""

# The measures compared per question, in the order they are reported. Each is
# recorded per question and averaged, so each can carry a paired interval.
MEASURES = ("relevant", "supported", "retrieved")


@dataclass(frozen=True, slots=True)
class Judged:
    """What one answer is judged on, and everything the judge needs to do it.

    The cited documents travel with the answer because support cannot be checked
    without them, and a judge handed the question and the prose alone would be
    grading its own knowledge of the series instead.
    """

    text: str
    citations: list[str]
    cited_documents: str
    # Not shown to the judge's rubrics; read by `RetrievedTheAnswer` below.
    retrieved: list[str] = field(default_factory=list[str])


# This class is a prompt as much as a type, in the way `Answer` is: its docstring
# and field descriptions are the schema the judge fills in.
@dataclass(frozen=True, slots=True)
class Verdict:
    """Whether the answer meets the rubric, and why."""

    passes: Annotated[bool, Field(description="True when the rubric is met.")]
    reason: Annotated[
        str, Field(description="One or two sentences justifying the verdict.")
    ]


# Ours rather than the one `pydantic_evals.evaluators.LLMJudge` builds, for two
# reasons. It carries the project's name into the traces, beside the agent it
# grades. And the rubrics are only pinned if the prompt around them is: a judge
# prompt that moves under a dependency upgrade would silently change every
# verdict after it.
judge = Agent(
    output_type=Verdict,
    instructions=JUDGE_INSTRUCTIONS,
    name="supernatural-expert-judge",
)


@dataclass(repr=False)
class RubricJudge(Evaluator[str, Judged, str]):
    """Grade one answer against one rubric, and record why.

    One evaluator per rubric rather than one asking for both, so a verdict is a
    verdict rather than a compromise between two, and so each carries its own
    paired interval.
    """

    measure: str
    rubric: str
    model: Model

    async def evaluate(
        self, ctx: EvaluatorContext[str, Judged, str]
    ) -> Mapping[str, EvaluationReason]:
        result = await judge.run(
            f"<rubric>{self.rubric}</rubric>\n"
            f"<question>{ctx.inputs}</question>\n"
            f"<answer>{ctx.output.text}</answer>\n"
            f"<cited_documents>{ctx.output.cited_documents}</cited_documents>",
            model=self.model,
        )
        return {
            self.measure: EvaluationReason(
                value=result.output.passes, reason=result.output.reason
            )
        }

    # The model is a live client, and the default serialization would try to
    # write it into the report. The rubric identifies the evaluator anyway.
    def build_serialization_arguments(self) -> dict[str, object]:
        return {"measure": self.measure, "rubric": self.rubric, "model": JUDGE_MODEL}


@dataclass(repr=False)
class RetrievedTheAnswer(Evaluator[str, Judged, str]):
    """Say whether search reached the labelled document at all, for free.

    This is the one measure here that costs nothing and needs no model, and it is
    what separates a bad answer from a bad retrieval underneath it. It is also
    the closest thing to the retrieval scores, run through the agent's own
    queries rather than the question as written.
    """

    # A mapping so the report names the result rather than the class.
    def evaluate(self, ctx: EvaluatorContext[str, Judged, str]) -> Mapping[str, bool]:
        return {"retrieved": ctx.metadata in ctx.output.retrieved}


def build_judge(settings: Settings) -> OpenAIResponsesModel:
    """Return the judge, holding the key rather than finding it."""
    return OpenAIResponsesModel(
        JUDGE_MODEL,
        provider=OpenAIProvider(api_key=settings.require_openai_api_key()),
    )


def build_dataset(
    questions: Sequence[Question], judge_model: Model
) -> Dataset[str, Judged, str]:
    """Turn the committed subset into cases both setups answer identically.

    The case name carries the position, so two setups line up question by
    question afterwards however the runs were ordered.
    """
    return Dataset[str, Judged, str](
        name="supernatural-expert answers",
        cases=[
            Case(
                name=f"{index:03d}-{question.document_id}",
                inputs=question.text,
                metadata=question.document_id,
            )
            for index, question in enumerate(questions)
        ],
        evaluators=[
            RubricJudge(measure="relevant", rubric=RELEVANCE_RUBRIC, model=judge_model),
            RubricJudge(measure="supported", rubric=SUPPORT_RUBRIC, model=judge_model),
            RetrievedTheAnswer(),
        ],
    )


def build_task(
    engine: SearchEngine, model: OpenAIResponsesModel, documents: int
) -> Callable[[str], Judged]:
    """Return the callable one setup answers with.

    The document count is closed over rather than passed per case, because it is
    the setup and not the question. Dependencies are rebuilt per question for the
    reason they are in the chat: a citation is checked against what that question
    retrieved.
    """

    def answer(question: str) -> Judged:
        deps = AnswerDeps(engine=engine, documents=documents)
        result = ask(question, deps, model)
        # Tokens are the cost side of the comparison. Without them "fewer
        # documents is cheaper" stays an assumption rather than a number.
        increment_eval_metric("tokens", result.usage.total_tokens)
        cited = [deps.retrieved[document_id] for document_id in result.output.citations]
        return Judged(
            text=result.output.text,
            citations=result.output.citations,
            cited_documents="\n\n".join(
                f"[{document.document_id}] {document.title}\n{document.content}"
                for document in cited
            ),
            retrieved=sorted(deps.retrieved),
        )

    return answer


def verdicts(
    report: EvaluationReport[str, Judged, str],
    names: Sequence[str],
    measure: str,
) -> list[float]:
    """Lift one measure out of a report, in the case order both setups share.

    A case that failed outright counts as a failed verdict rather than being
    dropped, because dropping it would let a setup improve its average by
    crashing on the questions it handles worst.
    """
    scored = {
        case.name: float(case.assertions[measure].value)
        for case in report.cases
        if measure in case.assertions
    }
    return [scored.get(name, 0.0) for name in names]


def mean_tokens(report: EvaluationReport[str, Judged, str]) -> float:
    """Return the average tokens one answer cost, over the cases that finished."""
    counts = [
        case.metrics["tokens"] for case in report.cases if "tokens" in case.metrics
    ]
    return sum(counts) / len(counts) if counts else 0.0


def _decimal(value: float) -> str:
    return f"{value:.3f}"


def verdict_rows(
    report: EvaluationReport[str, Judged, str],
    questions: Sequence[Question],
    names: Sequence[str],
) -> list[list[str]]:
    """Return every verdict with the reason the judge gave for it.

    A case that failed outright still gets a row per measure, because a question
    missing from this file would read as one that was never asked.
    """
    scored = {case.name: case for case in report.cases}
    rows: list[list[str]] = []
    for name, question in zip(names, questions):
        case = scored.get(name)
        for measure in MEASURES:
            assertion = case.assertions.get(measure) if case else None
            if assertion is None:
                rows.append([question.text, measure, "", "The case did not finish."])
                continue
            rows.append(
                [
                    question.text,
                    measure,
                    "pass" if assertion.value else "fail",
                    assertion.reason or "",
                ]
            )
    return rows


def write_scores(
    path: Path, rows: Sequence[Sequence[str]], header: Sequence[str]
) -> None:
    """Write one results table, quoted like every other evaluation artifact."""
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, quoting=csv.QUOTE_ALL)
        writer.writerow(header)
        writer.writerows(rows)


def main() -> int:
    settings = load_settings()
    configure_telemetry(settings)

    if "--held-out" in sys.argv[1:]:
        _, questions = split(load_questions(), load_held_out())
        scores_file, verdicts_file = HELD_OUT_SCORES_FILE, HELD_OUT_VERDICTS_FILE
        print(f"Reading {len(questions)} held-out questions, once.")
    else:
        questions = load_answer_subset(SUBSET_FILE)
        scores_file, verdicts_file = SCORES_FILE, VERDICTS_FILE
        print(f"Scoring {len(questions)} tuning questions.")

    names = [f"{index:03d}-{q.document_id}" for index, q in enumerate(questions)]

    model = build_model(settings)
    dataset = build_dataset(questions, build_judge(settings))

    connection = connect(settings)
    try:
        report = dataset.evaluate_sync(
            build_task(SearchEngine(connection), model, ANSWER_DOCUMENTS),
            name=f"answers-{ANSWER_DOCUMENTS}-documents",
            # SearchEngine is not thread-safe and pydantic-evals runs a
            # synchronous task in a worker thread, so cases run one at a time.
            max_concurrency=1,
        )
    finally:
        connection.close()

    measured = {measure: verdicts(report, names, measure) for measure in MEASURES}

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    write_scores(
        scores_file,
        [
            [
                f"{ANSWER_DOCUMENTS} documents",
                str(len(questions)),
                *(
                    _decimal(sum(measured[measure]) / len(questions))
                    for measure in MEASURES
                ),
                _decimal(mean_tokens(report)),
            ]
        ],
        ["setup", "questions", *MEASURES, "mean_tokens"],
    )

    write_scores(
        verdicts_file,
        verdict_rows(report, questions, names),
        ["question", "measure", "verdict", "reason"],
    )

    print(f"Wrote {scores_file} and {verdicts_file}.")
    for measure in MEASURES:
        print(f"{measure}: {_decimal(sum(measured[measure]) / len(questions))}")
    print(f"mean_tokens: {_decimal(mean_tokens(report))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
