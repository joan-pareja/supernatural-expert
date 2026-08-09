"""Entry point: `uv run python -m supernatural_expert.agent "your question"`."""

import sys

from supernatural_expert.agent.answering import main

if __name__ == "__main__":
    sys.exit(main())
