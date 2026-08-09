"""The ONNX cross-encoder this project can run, and where it lives on disk.

A reranker is pinned to a commit for the same reason an encoder is: a run today
and a run next month must score the same pair identically, or a comparison
between them means nothing.

It is a separate type from `EmbeddingModel` rather than another entry beside the
encoders. A cross-encoder has no dimensions, no pooling, and no query marker,
because it never produces a vector; it reads a query and a passage together and
returns one number. Giving it those fields would invite a caller to trust them.
"""

from dataclasses import dataclass
from pathlib import Path

from supernatural_expert.embedding.models import MODELS_DIR


@dataclass(frozen=True, slots=True)
class RerankerModel:
    """One downloadable ONNX cross-encoder and the facts callers need about it."""

    repository: str
    revision: str
    # The query and the passage share this window, so a long passage is truncated
    # to fit beside the query rather than each being measured alone.
    max_tokens: int

    def __post_init__(self) -> None:
        if not 0 < self.max_tokens <= 512:
            raise ValueError(
                f"{self.repository} sets max_tokens={self.max_tokens}, "
                "outside the 1 to 512 positions a BERT encoder has."
            )

    @property
    def directory(self) -> Path:
        return MODELS_DIR / self.repository

    @property
    def download_command(self) -> str:
        return "uv run python -m supernatural_expert.reranking"


# Xenova republishes the sentence-transformers cross-encoder in ONNX form.
#
# ms-marco-MiniLM-L-6-v2 is trained on real search queries paired with passages
# marked relevant or not, which is a narrower skill than the sentence similarity
# an embedding model learns. It runs on the same CPU as the encoder and ships 91
# MB of weights against the encoder's 128 MB. See docs/retrieval.md.
MS_MARCO_MINILM_L6_V2 = RerankerModel(
    repository="Xenova/ms-marco-MiniLM-L-6-v2",
    revision="a09144355adeed5f58c8ed011d209bf8ee5a1fec",
    max_tokens=512,
)

DEFAULT_RERANKER = MS_MARCO_MINILM_L6_V2
