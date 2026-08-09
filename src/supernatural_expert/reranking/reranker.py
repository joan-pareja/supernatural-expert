"""Score query and passage together with an ONNX cross-encoder, on CPU.

The difference from the encoder is where the query enters. An embedding model
compresses a passage into a vector before any question exists, so that summary
has to serve every question anyone might ask. A cross-encoder takes the query and
the passage as one input, so attention runs between them and the score reflects
this pair. Nothing can be precomputed, which is why this reads a shortlist and
never a corpus. See docs/retrieval.md.
"""

from typing import Any, cast

import numpy as np
import onnxruntime as ort
from numpy.typing import NDArray

from supernatural_expert.embedding.encoder import (
    ModelNotDownloadedError,
    load_tokenizer,
)
from supernatural_expert.reranking.models import DEFAULT_RERANKER, RerankerModel


class Reranker:
    """Scores passages against one query with an ONNX cross-encoder.

    Construction loads the weights, so build one and reuse it. Instances are not
    thread-safe, for the same reason the encoder is not: scoring reconfigures the
    shared tokenizer.
    """

    def __init__(self, model: RerankerModel = DEFAULT_RERANKER) -> None:
        self.model = model
        weights = model.directory / "model.onnx"
        if not weights.is_file():
            raise ModelNotDownloadedError(
                f"{model.repository} is missing model.onnx in {model.directory}. "
                f"Run: {model.download_command}"
            )

        self._tokenizer = load_tokenizer(model)
        # The pair shares one window, so the limit applies to the two together
        # and the passage is what gives way. See RerankerModel.max_tokens.
        self._tokenizer.enable_truncation(  # pyright: ignore[reportUnknownMemberType]
            max_length=model.max_tokens
        )
        self._tokenizer.enable_padding()  # pyright: ignore[reportUnknownMemberType]
        self._session = ort.InferenceSession(
            str(weights), providers=["CPUExecutionProvider"]
        )
        # A cross-encoder needs token_type_ids to tell the query from the
        # passage, but the feed still follows what this graph declares rather
        # than what the architecture usually wants.
        declared = cast(
            list[Any],
            self._session.get_inputs(),  # pyright: ignore[reportUnknownMemberType]
        )
        self._input_names: set[str] = {str(item.name) for item in declared}

    def score(self, query: str, passages: list[str]) -> list[float]:
        """Return one relevance score per passage, in the order given.

        Scores are raw logits. They order passages within one query and mean
        nothing across queries, so they are compared and never averaged.
        """
        if not passages:
            return []

        encoded = self._tokenizer.encode_batch(
            [(query, passage) for passage in passages]
        )
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
        logits = cast(NDArray[np.float32], outputs[0])
        if logits.ndim != 2 or logits.shape[1] != 1:
            raise ValueError(
                f"{self.model.repository} returned logits of shape {logits.shape}, "
                "not one relevance score per pair."
            )
        return [float(value) for value in logits[:, 0]]
