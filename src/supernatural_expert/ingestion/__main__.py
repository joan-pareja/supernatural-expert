"""Entry point for `uv run python -m supernatural_expert.ingestion`."""

import sys

from supernatural_expert.ingestion.pipeline import main

if __name__ == "__main__":
    sys.exit(main())
