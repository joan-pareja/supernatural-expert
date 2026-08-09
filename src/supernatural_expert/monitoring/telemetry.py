"""Sends traces to Logfire, when a write token says to.

Configuring is a process-wide act, so it belongs at an entry point and nowhere
else: the command line does it before it answers, and the chat does it once
behind the cache that opens the model and the database. Importing this module
sends nothing.

The token is passed rather than found. Logfire reads `LOGFIRE_TOKEN` from the
process environment on its own, and the project's token is deliberately spelled
`LOGFIRE_WRITE_TOKEN` so that cannot happen. See docs/monitoring.md.
"""

import logfire

from supernatural_expert.config import Settings

SERVICE_NAME = "supernatural-expert"


def configure_telemetry(settings: Settings) -> bool:
    """Wire Logfire and instrument the agent. Return whether anything is sent.

    `if-token-present` is what makes telemetry optional: with no token the SDK
    stays in place, spans are still opened, and nothing leaves the machine.
    Console output stays off because a full agent trace is unreadable in a
    terminal and Logfire is where it is meant to be read.

    Instrumenting Pydantic AI covers the model calls, the tool calls, the token
    usage, and the timings of each. Only work it cannot see needs a span of its
    own.
    """
    logfire.configure(
        token=settings.logfire_write_token,
        send_to_logfire="if-token-present",
        service_name=SERVICE_NAME,
        console=False,
    )
    logfire.instrument_pydantic_ai()
    return settings.logfire_write_token is not None
