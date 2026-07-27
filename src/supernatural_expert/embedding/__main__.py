"""Entry point for `uv run python -m supernatural_expert.embedding`."""

import sys

from supernatural_expert.embedding.download import main

if __name__ == "__main__":
    sys.exit(main())
