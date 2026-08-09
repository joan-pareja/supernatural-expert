"""Fetch the pinned cross-encoder into `models/`, ready for the reranker.

The fetch itself belongs to `supernatural_expert.embedding.download`, which does
not care what a graph computes. Only the model being asked for differs.
"""

from supernatural_expert.embedding.download import download_model
from supernatural_expert.reranking.models import DEFAULT_RERANKER


def main() -> int:
    model = DEFAULT_RERANKER
    print(f"{model.repository} at {model.revision[:7]}")
    directory = download_model(model)
    print(f"Ready. {model.max_tokens} tokens across query and passage, {directory}")
    return 0
