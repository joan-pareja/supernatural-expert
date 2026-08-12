"""Tests for the answering agent, with a scripted model and a stub engine.

No model is called and no database is read. What these pin is the part of the
agent that is ours rather than Pydantic AI's: the first search carries the
question word for word, the tool reaches search with the arguments the model
chose, follow-up searches run out, every document returned stays resolvable as a
citation, and a citation for anything else does not survive the run.
"""

from typing import cast

from pydantic_ai.messages import ModelMessage, ModelResponse, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.openai import OpenAIResponsesModel

from supernatural_expert.agent.answering import (
    ANSWER_DOCUMENTS,
    FOLLOW_UP_SEARCHES,
    Answer,
    AnswerDeps,
    ask,
    expert,
)
from supernatural_expert.search.engine import SearchEngine, SearchFilters, SearchResult

SEARCH_TOOL = "search_episodes"


def result(document_id: str, season: int, episode: int) -> SearchResult:
    return SearchResult(
        document_id=document_id,
        title=f"Episode {episode}",
        season_number=season,
        episode_number=episode,
        content="A hunter salts and burns the bones.",
        source_url=f"https://en.wikipedia.org/wiki/{document_id}",
        score=1.0,
        matched_text="salts and burns",
    )


class StubEngine:
    """A search engine that answers from a fixed list and records every call."""

    def __init__(self, results: list[SearchResult]) -> None:
        self.results = results
        self.calls: list[tuple[str, int, SearchFilters]] = []
        self.reranked = False

    def search(
        self,
        query: str,
        path: str = "hybrid",
        limit: int = 10,
        filters: SearchFilters | None = None,
        candidates: int = 50,
        rerank: bool = False,
    ) -> list[SearchResult]:
        self.calls.append((query, limit, filters or SearchFilters()))
        self.reranked = rerank
        return self.results


def deps_for(*results: SearchResult) -> tuple[AnswerDeps, StubEngine]:
    engine = StubEngine(list(results))
    return AnswerDeps(engine=cast(SearchEngine, engine)), engine


def scripted(*replies: list[ToolCallPart]) -> FunctionModel:
    """Return a model that plays one prepared reply per turn, in order."""
    turns = iter(replies)

    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=next(turns))

    return FunctionModel(respond)


def answer_call(text: str, citations: list[str]) -> ToolCallPart:
    return ToolCallPart("final_result", {"text": text, "citations": citations})


def test_the_tool_searches_with_what_the_model_chose() -> None:
    deps, engine = deps_for(result("s02e13", 2, 13))
    model = scripted(
        [ToolCallPart(SEARCH_TOOL, {"query": "the Roadhouse", "season": 2})],
        [answer_call("It burns down.", ["s02e13"])],
    )

    run = expert.run_sync("What happens to the Roadhouse?", deps=deps, model=model)

    query, limit, filters = engine.calls[0]
    assert (query, filters.season, filters.episode) == ("the Roadhouse", 2, None)
    assert limit == ANSWER_DOCUMENTS
    # Reranking is the tool's to set, never the model's, so it is on every call.
    assert engine.reranked
    assert run.output == Answer(text="It burns down.", citations=["s02e13"])


def test_every_retrieved_document_resolves_to_its_source() -> None:
    deps, _ = deps_for(result("s01e01", 1, 1), result("s01e02", 1, 2))
    model = scripted(
        [ToolCallPart(SEARCH_TOOL, {"query": "the pilot"})],
        [answer_call("Two brothers hunt.", ["s01e01"])],
    )

    expert.run_sync("How does it open?", deps=deps, model=model)

    assert set(deps.retrieved) == {"s01e01", "s01e02"}
    assert deps.retrieved["s01e01"].source_url.endswith("s01e01")


def test_the_first_search_is_the_question_word_for_word() -> None:
    question = "when do they get the gun that kills anything"
    deps, engine = deps_for(result("s01e22", 1, 22))
    # The model answers without searching, so any call the engine saw is ask's.
    model = scripted([answer_call("The Colt.", ["s01e22"])])

    ask(question, deps, cast(OpenAIResponsesModel, model))

    assert engine.calls[0][0] == question
    # The verbatim search is not the model's to spend.
    assert deps.searches == 0


def test_the_model_runs_out_of_follow_up_searches() -> None:
    deps, engine = deps_for(result("s03e09", 3, 9))
    attempts = [
        [ToolCallPart(SEARCH_TOOL, {"query": f"rewording {number}"})]
        for number in range(FOLLOW_UP_SEARCHES + 1)
    ]
    model = scripted(*attempts, [answer_call("Pagan gods.", ["s03e09"])])

    run = expert.run_sync("Which episode is about Christmas?", deps=deps, model=model)

    # The search past the budget is refused rather than run, and the model is
    # told so and answers from what it already had.
    assert len(engine.calls) == FOLLOW_UP_SEARCHES
    assert deps.searches == FOLLOW_UP_SEARCHES
    assert run.output == Answer(text="Pagan gods.", citations=["s03e09"])


def test_an_invented_citation_is_sent_back() -> None:
    deps, _ = deps_for(result("s03e09", 3, 9))
    model = scripted(
        [ToolCallPart(SEARCH_TOOL, {"query": "Christmas"})],
        [answer_call("Pagan gods.", ["s03e09", "s07e01"])],
        [answer_call("Pagan gods.", ["s03e09"])],
    )

    run = expert.run_sync("Which episode is about Christmas?", deps=deps, model=model)

    assert run.output.citations == ["s03e09"]
