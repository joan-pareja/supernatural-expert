"""Entry point for `uv run python -m supernatural_expert.reranking`."""

import sys

from supernatural_expert.reranking.download import main

if __name__ == "__main__":
    sys.exit(main())
