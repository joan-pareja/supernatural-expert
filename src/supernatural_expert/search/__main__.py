"""Entry point: `uv run python -m supernatural_expert.search` rebuilds the index."""

import sys

from supernatural_expert.search.index import main

if __name__ == "__main__":
    sys.exit(main())
