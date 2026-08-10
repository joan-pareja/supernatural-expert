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

import logfire
import streamlit as st
from logfire.experimental.annotations import get_traceparent, record_feedback
from pydantic_ai.models.openai import OpenAIResponsesModel

from supernatural_expert.agent.answering import (
    AnswerDeps,
    RetrievedDocument,
    ask,
    build_model,
)
from supernatural_expert.config import load_settings
from supernatural_expert.monitoring.telemetry import configure_telemetry
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

# What st.feedback returns for the up thumb; the down thumb is 0.
THUMBS_UP = 1
FEEDBACK_NAME = "thumbs_up"


@dataclass(frozen=True, slots=True)
class Exchange:
    """One question and its answer, kept so a rerun can redraw the conversation.

    `traceparent` is what lets a thumb clicked minutes later reach the turn it
    judges. Feedback is sent from a rerun of its own, long after the run's spans
    have closed, so the trace has to be remembered rather than rediscovered.
    """

    question: str
    answer: str
    sources: list[RetrievedDocument]
    traceparent: str


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

    Telemetry is configured here for the same reason it is cached rather than for
    what it costs: it is process-wide, and Streamlit reruns this file on every
    keystroke it handles.
    """
    settings = load_settings()
    configure_telemetry(settings)
    return Expert(
        model=build_model(settings),
        engine=SearchEngine(connect(settings)),
        lock=Lock(),
    )


def exchanges() -> list[Exchange]:
    """Return this session's conversation, empty on the first run."""
    return cast(list[Exchange], st.session_state.setdefault("exchanges", []))


def remember(traceparent: str) -> None:
    """Attach the thumb to its turn in Logfire.

    Streamlit calls this only when the widget changes, so a thumb is sent once
    rather than on every rerun that redraws it. The traceparent is also the
    widget key, which is what makes the reading possible here.
    """
    thumb = st.session_state[traceparent]
    record_feedback(traceparent, FEEDBACK_NAME, thumb == THUMBS_UP)


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
        # Keyed by the traceparent because it identifies the turn and is unique
        # per answer, so every drawn exchange keeps its own thumb across reruns.
        st.feedback(
            "thumbs",
            key=exchange.traceparent,
            on_change=remember,
            args=(exchange.traceparent,),
        )


def answer(expert: Expert, question: str) -> Exchange:
    """Run the agent on one question and collect what it cited.

    The dependencies are built fresh so this run's citations are checked against
    this run's own search results. The message history is not: it carries the
    earlier turns, which is what lets a follow-up say "that episode".

    The span is the one place the project opens one, and it is here because a
    thumb needs something to attach to: instrumentation's own spans are closed by
    the time the buttons are drawn, and none of them is reachable afterwards. It
    is also the turn as the viewer experiences it, waiting for the lock included,
    which the agent run inside it is not.
    """
    deps = AnswerDeps(engine=expert.engine)
    with logfire.span("chat turn") as turn:
        traceparent = get_traceparent(turn)
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
        traceparent=traceparent,
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
