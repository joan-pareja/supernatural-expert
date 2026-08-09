"""Turn text into normalized vectors with onnxruntime, on CPU, with no torch.

Queries and documents get separate methods because retrieval is asymmetric: a
short question and the long passage answering it are different kinds of text, and
a retrieval-trained model expects the query to say so. Leaving that to callers
would mean every call site could silently forget it, so there is no way here to
encode a query without the query treatment.

Tokenizer settings are set here rather than trusted from the downloaded file. The
published `tokenizer.json` for these repositories carries truncation and padding
fixed at 128 tokens, well under the encoders' real limits, which would quietly
discard most of every corpus document.
"""

from typing import Any, cast

import numpy as np
import onnxruntime as ort
from numpy.typing import NDArray
from tokenizers import Tokenizer

from supernatural_expert.embedding.models import (
    DEFAULT_MODEL,
    EmbeddingModel,
    OnnxModel,
)

Vectors = NDArray[np.float32]


class ModelNotDownloadedError(RuntimeError):
    """Raised when a pinned model, encoder or reranker, is not on disk yet."""


def load_tokenizer(model: OnnxModel) -> Tokenizer:
    """Load a model's tokenizer with no truncation or padding applied.

    Callers add the limits they need. The chunker in particular must count the
    whole text, and would measure every long document as exactly one full chunk
    if it inherited the file's truncation.
    """
    path = model.directory / "tokenizer.json"
    if not path.is_file():
        raise ModelNotDownloadedError(
            f"{model.repository} is missing tokenizer.json in {model.directory}. "
            f"Run: {model.download_command}"
        )
    tokenizer = Tokenizer.from_file(str(path))
    tokenizer.no_truncation()  # pyright: ignore[reportUnknownMemberType]
    tokenizer.no_padding()  # pyright: ignore[reportUnknownMemberType]
    return tokenizer


class Encoder:
    """Encodes text with one ONNX model.

    Construction loads the weights, so build one and reuse it. Instances are not
    thread-safe: encoding reconfigures the shared tokenizer.
    """

    def __init__(self, model: EmbeddingModel = DEFAULT_MODEL) -> None:
        self.model = model
        weights = model.directory / "model.onnx"
        if not weights.is_file():
            raise ModelNotDownloadedError(
                f"{model.repository} is missing model.onnx in {model.directory}. "
                f"Run: {model.download_command}"
            )

        self._tokenizer = load_tokenizer(model)
        # onnxruntime and tokenizers ship stubs that leave these calls partially
        # typed. The ignores are per call, so the rest of the file stays strict.
        self._tokenizer.enable_truncation(  # pyright: ignore[reportUnknownMemberType]
            max_length=model.max_tokens
        )
        self._tokenizer.enable_padding()  # pyright: ignore[reportUnknownMemberType]
        self._session = ort.InferenceSession(
            str(weights), providers=["CPUExecutionProvider"]
        )
        # These encoders differ in whether they accept token_type_ids, so the
        # feed is built from what this graph actually declares.
        declared = cast(
            list[Any],
            self._session.get_inputs(),  # pyright: ignore[reportUnknownMemberType]
        )
        self._input_names: set[str] = {str(item.name) for item in declared}

    def encode_documents(self, texts: list[str]) -> Vectors:
        """Return one unit-length row per passage, in the order given."""
        if not texts:
            return np.zeros((0, self.model.dimensions), dtype=np.float32)
        return self._embed(texts)

    def encode_query(self, text: str) -> Vectors:
        """Return one unit-length vector for a search query."""
        return self._embed([self.model.query_prefix + text])[0]

    def token_count(self, text: str) -> int:
        """Tokens the encoder would actually read, after truncation."""
        return len(self._tokenizer.encode(text).ids)

    def _embed(self, texts: list[str]) -> Vectors:
        """Tokenize, run the model, collapse each text to one vector, scale to 1.

        The model returns a vector per token, so the sequence axis has to go:
        `(texts, tokens)` in, `(texts, tokens, dimensions)` from the graph, and
        `(texts, dimensions)` out.
        """
        encoded = self._tokenizer.encode_batch(texts)
        ids = np.array([item.ids for item in encoded], dtype=np.int64)
        mask = np.array([item.attention_mask for item in encoded], dtype=np.int64)
        feed: dict[str, NDArray[np.int64]] = {"input_ids": ids, "attention_mask": mask}
        if "token_type_ids" in self._input_names:
            feed["token_type_ids"] = np.array(
                [item.type_ids for item in encoded], dtype=np.int64
            )

        outputs = cast(
            list[Any],
            self._session.run(None, feed),  # pyright: ignore[reportUnknownMemberType]
        )
        hidden = cast(NDArray[np.float32], outputs[0])
        pooled = self._pool(hidden, mask)
        norms = np.linalg.norm(pooled, axis=1, keepdims=True)
        return cast(Vectors, pooled / norms)

    def _pool(self, hidden: Vectors, mask: NDArray[np.int64]) -> Vectors:
        if self.model.pooling == "cls":
            # These models were trained to collect the sentence meaning in the
            # leading [CLS] position, which is never a padding token.
            return hidden[:, 0]
        # Padding tokens carry a mask of 0, so they contribute to neither the
        # sum nor the divisor.
        weights = mask[:, :, None].astype(np.float32)
        return cast(Vectors, (hidden * weights).sum(axis=1) / weights.sum(axis=1))
