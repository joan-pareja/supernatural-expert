"""The agent that answers a question from retrieved episode text.

One model, one search tool, one checked answer. The first search is this module's
and runs before the model does: the question goes to search word for word,
because that was measured to reach the answering document more often than any
rewrite of it. Every search after that is the model's own, in its own wording and
at its own timing, up to a budget. See docs/agent.md.

Answers are grounded in two ways that do not depend on each other. The
instructions tell the model to write only from what search returned, which it can
disregard. The output validator rejects a citation for a document this run never
retrieved, which it cannot.

Everything is synchronous. psycopg2 and ONNX Runtime both block, so an async loop
would buy nothing here and would spread through every caller.
"""

import sys
from dataclasses import dataclass, field
from typing import Annotated

from opentelemetry import trace
from pydantic import Field
from pydantic_ai import (
    Agent,
    AgentRunResult,
    ModelMessage,
    ModelRetry,
    RunContext,
    UsageLimits,
)
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider

from supernatural_expert.config import Settings, load_settings
from supernatural_expert.monitoring.telemetry import configure_telemetry
from supernatural_expert.search.engine import SearchEngine, SearchFilters, SearchPath
from supernatural_expert.search.index import connect

ANSWER_MODEL = "gpt-5.6-luna"

# What an answer searches with, settled by the measurements in
# docs/evaluation.md rather than chosen per question. Reranking is the tool's to
# set and never the model's: a model choosing it would turn an ordering
# guarantee into a preference.
SEARCH_PATH: SearchPath = "hybrid"
RERANK_ANSWERS = True

# Searches the model may run for itself, after the verbatim one `ask` has already
# run. Traces showed a turn spending six searches on five rewordings of the same
# question, two of them returning identical documents, so this is a budget rather
# than a safety valve.
FOLLOW_UP_SEARCHES = 2

# The hard stop behind the budget. `tool_calls_limit` aborts the run rather than
# letting the model answer, so it sits above the budget the tool enforces
# gracefully and only fires if that fails.
SEARCH_BACKSTOP = FOLLOW_UP_SEARCHES + 2

# Documents one search hands the model. Each carries a whole episode plot, so
# this is a context budget as much as a recall setting: past a handful, the
# answer is written from more text than any question needs.
#
# The default rather than the setting. It sits on AnswerDeps so answer evaluation
# can run two counts against each other in one process, which is the comparison
# docs/evaluation.md settles this number on.
ANSWER_DOCUMENTS = 3

INSTRUCTIONS = """
You answer questions about the television series Supernatural, seasons 1 to 6,
for a viewer who is watching it now.

The question has already been searched word for word, and the results arrive with
it. Write the answer only from search results.

Search again when those results do not settle the question, and rewrite freely
then. A viewer describes things loosely while the documents carry the show's own
names for them, so a search written in the series' vocabulary finds what the
first could not.

You may search twice more at most, so make each one a different line of attack
rather than another wording of the same one. Rewording a search that already
answered as well as it could returns the same documents again.

Leave the season and episode filters unset unless the question names one.
Narrowing to a season inferred from earlier results hides every document outside
it, the answer included.

Answer at the level of detail the documents hold, and stop where they stop. Do
not explain why something happened unless a document says why, do not name anyone
the documents leave unnamed, and do not join two facts into a cause the documents
do not state. A sentence that reads as the natural next thing to say is the one
most likely to be yours rather than theirs.

Cite every document the answer rests on by its document_id.

Say plainly that the corpus does not cover it when the results do not hold the
answer, and cite nothing. Never close the gap with what you already know about
the show.

The corpus stops at the end of season 6. Treat anything later as a spoiler: say
you cannot go past season 6, even when you know the answer, and do not hint at
it.
"""


@dataclass(frozen=True, slots=True)
class RetrievedDocument:
    """One search result, as the model reads it and as a citation resolves to.

    `content` is the whole document rather than the piece that matched, because a
    piece is enough to find an episode and not enough to describe one.
    """

    document_id: str
    title: str
    season_number: int
    episode_number: int | None
    content: str
    source_url: str


# This class is a prompt as much as a type. Its docstring and every field
# description are sent to the model as the schema it must fill in, so they are
# written for the model; what a reader of this module needs is in comments.
#
# Callers resolve each citation against the run's `AnswerDeps.retrieved` to get a
# title and a Wikipedia link. The model never writes a URL and so cannot write a
# wrong one.
@dataclass(frozen=True, slots=True)
class Answer:
    """The answer to the question, and the documents it rests on."""

    text: Annotated[
        str,
        Field(description="The answer, written for someone watching the series."),
    ]
    citations: Annotated[
        list[str],
        Field(
            description=(
                "The document_id of every document the answer rests on, such as "
                "'s02e13'. Never a title, a URL, or an episode name. Empty when "
                "the corpus does not answer the question."
            )
        ),
    ]


@dataclass(slots=True)
class AnswerDeps:
    """What one run searches with, and what that run found.

    The engine and `retrieved` have to arrive per run rather than be settled
    here: the engine holds a connection that does not exist until the process
    starts, and `retrieved` is this run's own record. `documents` defaults to the
    adopted count and is overridden only by the evaluation that compares counts.

    `retrieved` accumulates every document the tool returned, which is what makes
    a citation checkable and what turns a document_id back into a link. Build a
    fresh instance for each question, or one run's documents would vouch for the
    next one's citations.
    """

    engine: SearchEngine
    documents: int = ANSWER_DOCUMENTS
    # The factory is parameterised so the empty dictionary has the field's type.
    retrieved: dict[str, RetrievedDocument] = field(
        default_factory=dict[str, RetrievedDocument]
    )
    # Searches the model has run for itself. The verbatim one is not counted,
    # because it is not the model's to spend.
    searches: int = 0


# The verbatim search runs outside the agent, so Pydantic AI opens no span around
# it and this is the only way it appears in a trace at all. The rule the tool
# follows is unchanged: nothing opens a second span over work the library already
# covers. See docs/monitoring.md.
tracer = trace.get_tracer("supernatural_expert.agent")

expert = Agent(
    deps_type=AnswerDeps,
    output_type=Answer,
    instructions=INSTRUCTIONS,
    name="supernatural-expert",
)


def run_search(
    deps: AnswerDeps, query: str, filters: SearchFilters | None = None
) -> list[RetrievedDocument]:
    """Search, record what search did, and remember what it returned.

    Both searches in a turn come through here: the verbatim one `ask` runs and
    every rewrite the model asks for afterwards. Sharing it is what lets one
    query read both, because the `search.*` attributes below land on whichever
    span is running rather than on a span this function chooses.

    The settings are recorded rather than assumed, so a trace still explains
    itself after they change, and the ranked ids are lifted out of the result
    because a query across traces should not have to parse five episode plots to
    learn which documents came back. Without a configured Logfire these calls
    land on a non-recording span and do nothing.
    """
    results = deps.engine.search(
        query,
        path=SEARCH_PATH,
        limit=deps.documents,
        filters=filters or SearchFilters(),
        rerank=RERANK_ANSWERS,
    )
    span = trace.get_current_span()
    span.set_attribute("search.path", SEARCH_PATH)
    span.set_attribute("search.rerank", RERANK_ANSWERS)
    span.set_attribute("search.limit", deps.documents)
    span.set_attribute("search.documents", [result.document_id for result in results])
    documents = [
        RetrievedDocument(
            document_id=result.document_id,
            title=result.title,
            season_number=result.season_number,
            episode_number=result.episode_number,
            content=result.content,
            source_url=result.source_url,
        )
        for result in results
    ]
    deps.retrieved.update({document.document_id: document for document in documents})
    return documents


# The retry budget is the model's room to be told its searches are spent and to
# answer anyway. One is the default and would be consumed by a single refusal.
@expert.tool(retries=3)
def search_episodes(
    ctx: RunContext[AnswerDeps],
    query: str,
    season: int | None = None,
    episode: int | None = None,
) -> list[RetrievedDocument]:
    """Search Supernatural episode and season documents, best match first.

    Args:
        query: What to look for, in plain words. Names of characters, towns, and
            objects narrow it far more than plot words do.
        season: Restrict to one season, 1 to 6. Leave unset unless the question
            names a season, because a wrong guess hides the answer.
        episode: Restrict to one episode number within `season`. Leave unset
            unless the question names an episode number.
    """
    # Refusing here rather than through `tool_calls_limit`, which raises and ends
    # the run with no answer at all. The model is told the budget is spent and
    # writes from what it already has, which is what a viewer should get.
    if ctx.deps.searches >= FOLLOW_UP_SEARCHES:
        raise ModelRetry(
            f"No searches left: {FOLLOW_UP_SEARCHES} follow-ups is the limit. "
            "Answer from the documents already retrieved, or say the corpus does "
            "not cover the question."
        )
    ctx.deps.searches += 1
    # The tool's own span is the one running here, and instrumentation already
    # recorded the arguments and the result on it, so nothing opens a second span
    # around the same work.
    return run_search(ctx.deps, query, SearchFilters(season=season, episode=episode))


@expert.output_validator
def check_citations(ctx: RunContext[AnswerDeps], answer: Answer) -> Answer:
    """Reject any citation this run did not retrieve.

    A model that has read five documents can still cite a sixth it remembers, and
    a citation is worth exactly as much as the guarantee behind it. Raising here
    sends the answer back for another attempt rather than dropping the citation,
    because a claim whose support is invented is usually wrong about more than
    the support.
    """
    invented = [
        document_id
        for document_id in answer.citations
        if document_id not in ctx.deps.retrieved
    ]
    if invented:
        raise ModelRetry(
            f"Search never returned these documents: {', '.join(invented)}. "
            "Cite only document_id values from search results, and drop any claim "
            "left without one."
        )
    return answer


def build_model(settings: Settings) -> OpenAIResponsesModel:
    """Return the answer model, holding the key rather than finding it.

    The provider is given the key explicitly so the OpenAI SDK never reads
    OPENAI_API_KEY from the process environment.
    """
    return OpenAIResponsesModel(
        ANSWER_MODEL,
        provider=OpenAIProvider(api_key=settings.require_openai_api_key()),
    )


def render_documents(documents: list[RetrievedDocument]) -> str:
    """Lay the verbatim search out for the model, as the tool's results arrive."""
    if not documents:
        return "Nothing was found."
    return "\n\n".join(
        f"[{document.document_id}] {document.title}\n{document.content}"
        for document in documents
    )


def ask(
    question: str,
    deps: AnswerDeps,
    model: OpenAIResponsesModel,
    message_history: list[ModelMessage] | None = None,
) -> AgentRunResult[Answer]:
    """Answer one question and return the whole run.

    The result rather than the answer, because a caller holding a conversation
    needs `all_messages()` for the next turn, and one measuring the run needs its
    usage. `message_history` carries the earlier turns; without it every question
    stands alone.

    The question is searched word for word here rather than asked for in the
    instructions. Measurement put the agent's own phrasing about six points below
    the question as asked, and a trace showed the model rewriting the first
    search anyway: an instruction is a request, and this is the one search worth
    a guarantee. What the model does afterwards is still its own.
    """
    with tracer.start_as_current_span("search_episodes verbatim"):
        documents = run_search(deps, question)

    return expert.run_sync(
        f"{question}\n\n"
        "<search_results>\n"
        "Searching the question above word for word returned:\n\n"
        f"{render_documents(documents)}\n"
        "</search_results>",
        deps=deps,
        model=model,
        message_history=message_history,
        usage_limits=UsageLimits(tool_calls_limit=SEARCH_BACKSTOP),
    )


def main() -> int:
    question = " ".join(sys.argv[1:]).strip()
    if not question:
        print('Ask something: uv run python -m supernatural_expert.agent "question"')
        return 2

    settings = load_settings()
    configure_telemetry(settings)
    model = build_model(settings)

    connection = connect(settings)
    try:
        deps = AnswerDeps(engine=SearchEngine(connection))
        answer = ask(question, deps, model).output
    finally:
        connection.close()

    print(answer.text)
    for document_id in answer.citations:
        document = deps.retrieved[document_id]
        print(f"  {document_id}  {document.title}  {document.source_url}")
    return 0
