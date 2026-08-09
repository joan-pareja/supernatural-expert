"""Entry point: `uv run python -m supernatural_expert.evaluation` scores the paths."""

import sys

from supernatural_expert.evaluation.baseline import main

if __name__ == "__main__":
    sys.exit(main())
