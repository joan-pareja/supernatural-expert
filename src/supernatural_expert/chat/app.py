"""The chat page, and the only place the agent is reached from a browser.

Run it from the repository root:

    uv run streamlit run src/supernatural_expert/chat/app.py

Streamlit reruns this file top to bottom on every interaction, so the page is
rebuilt from `st.session_state` each time and only the expensive parts survive a
rerun. See docs/chat.md.
"""

from dataclasses import dataclass
from threading import Lock
from typing import cast

import streamlit as st
from pydantic_ai.models.openai import OpenAIResponsesModel

from supernatural_expert.agent.answering import (
    AnswerDeps,
    RetrievedDocument,
    ask,
    build_model,
)
from supernatural_expert.config import load_settings
from supernatural_expert.search.engine import SearchEngine
from supernatural_expert.search.index import connect

TITLE = "Supernatural expert"
SUBTITLE = "Ask about seasons 1 to 6. Answers come from Wikipedia, with sources."
PLACEHOLDER = "What happens to the Roadhouse?"

OPENING = """
Ask anything from the first six seasons, such as:

- Which episode introduces Castiel?
- How does Sam meet Ruby?
- What is the Colt and who made it?
"""


@dataclass(frozen=True, slots=True)
class Exchange:
    """One question and its answer, kept so a rerun can redraw the conversation."""

    question: str
    answer: str
    sources: list[RetrievedDocument]


@dataclass(frozen=True, slots=True)
class Expert:
    """The model and the search engine, opened once and shared by every session."""

    model: OpenAIResponsesModel
    engine: SearchEngine
    # SearchEngine is not thread-safe and Streamlit runs each browser session in
    # its own thread, so answers are taken one at a time.
    lock: Lock


@st.cache_resource(show_spinner="Waking the hunters...")
def load_expert() -> Expert:
    """Load the settings, the model, and the database connection once per server.

    Everything here costs seconds and none of it varies by question, which is why
    the page opens fast and a question does not pay for the connection again. The
    connection is deliberately never closed: it lives as long as the server does.
    """
    settings = load_settings()
    return Expert(
        model=build_model(settings),
        engine=SearchEngine(connect(settings)),
        lock=Lock(),
    )


def exchanges() -> list[Exchange]:
    """Return this session's conversation, empty on the first run."""
    return cast(list[Exchange], st.session_state.setdefault("exchanges", []))


def render(exchange: Exchange) -> None:
    with st.chat_message("user"):
        st.markdown(exchange.question)
    with st.chat_message("assistant"):
        st.markdown(exchange.answer)
        if exchange.sources:
            with st.expander(f"Sources ({len(exchange.sources)})"):
                for document in exchange.sources:
                    st.markdown(
                        f"[{document.title}]({document.source_url}) "
                        f"— `{document.document_id}`"
                    )


def answer(expert: Expert, question: str) -> Exchange:
    """Run the agent on one question and collect what it cited.

    The dependencies are built fresh so this run's citations are checked against
    this run's own search results. The message history is not: it carries the
    earlier turns, which is what lets a follow-up say "that episode".
    """
    deps = AnswerDeps(engine=expert.engine)
    with expert.lock:
        result = ask(
            question,
            deps,
            expert.model,
            message_history=st.session_state.get("history"),
        )
    st.session_state["history"] = result.all_messages()
    return Exchange(
        question=question,
        answer=result.output.text,
        sources=[
            deps.retrieved[document_id] for document_id in result.output.citations
        ],
    )


st.set_page_config(page_title=TITLE, page_icon="🕯️", layout="centered")

st.title(TITLE)
st.caption(SUBTITLE)

expert = load_expert()

if not exchanges():
    st.info(OPENING)

for past in exchanges():
    render(past)

question = st.chat_input(PLACEHOLDER)
if question:
    try:
        with st.spinner("Reading the episodes..."):
            current = answer(expert, question)
    except Exception as error:
        st.error(f"The question could not be answered: {error}")
    else:
        exchanges().append(current)
        render(current)
