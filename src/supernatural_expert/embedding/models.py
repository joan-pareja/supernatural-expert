"""The ONNX embedding models this project can run, and where they live on disk.

A model is named by its Hugging Face repository and pinned to a commit, for the
same reason ingestion pins a Wikipedia revision: a run today and a run next month
must produce the same vectors, or an evaluation comparing them is meaningless.

Everything an encoder has to do differently per model is a field here rather than
a branch in the encoder. Get one of these wrong and nothing raises; the vectors
are simply worse, which is the failure mode this shape exists to prevent.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from supernatural_expert.config import REPOSITORY_ROOT

# Weights are large and reproducible from the pinned revision, so they are
# downloaded rather than committed. See .gitignore.
MODELS_DIR = REPOSITORY_ROOT / "models"


class OnnxModel(Protocol):
    """All that fetching a model and loading its tokenizer need to know.

    Downloading and tokenizing care about a repository, a revision, and a place
    on disk, and nothing about what the graph computes. Stating that much as a
    protocol lets a cross-encoder, which has no dimensions and no query marker,
    reuse the same plumbing without pretending to be an encoder.
    """

    @property
    def repository(self) -> str: ...

    @property
    def revision(self) -> str: ...

    @property
    def directory(self) -> Path: ...

    @property
    def download_command(self) -> str: ...


@dataclass(frozen=True, slots=True)
class EmbeddingModel:
    """One downloadable ONNX encoder and the facts callers need about it."""

    repository: str
    revision: str
    dimensions: int
    # The encoder's own limit, from its sentence-transformers configuration.
    # Text beyond this is dropped, so it belongs in the model definition rather
    # than at a call site that cannot know it.
    max_tokens: int
    # Retrieval-trained models were shown queries wearing a marker and passages
    # wearing none, so a query has to arrive in that same shape. Models trained
    # for plain sentence similarity use no marker and leave this empty.
    query_prefix: str = ""

    def __post_init__(self) -> None:
        # Every model here is BERT-based and its position embeddings stop at 512.
        # A larger value would not error; it would return silent nonsense.
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
        return "uv run python -m supernatural_expert.embedding"


# Xenova republishes sentence-transformers and BAAI encoders in ONNX form.
#
# bge-small-en-v1.5 is the project's encoder. It was trained on question-to-passage
# pairs, which is the job here, while the course's all-MiniLM-L6-v2 was trained on
# general sentence similarity; BAAI reports 51.68 against 43.81 on MTEB retrieval
# for a model three times its size. Both are 384 dimensions. Indexing the whole
# corpus on CPU takes about twenty seconds, which is a cost per experiment rather
# than per query. See docs/retrieval.md.
BGE_SMALL_EN_V1_5 = EmbeddingModel(
    repository="Xenova/bge-small-en-v1.5",
    revision="ea104dacec62c0de699686887e3f920caeb4f3e3",
    dimensions=384,
    max_tokens=512,
    query_prefix="Represent this sentence for searching relevant passages: ",
)

DEFAULT_MODEL = BGE_SMALL_EN_V1_5
