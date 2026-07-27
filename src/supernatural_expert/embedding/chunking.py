"""Split a document into pieces the encoder can read whole.

An encoder reads a fixed number of tokens and silently ignores the rest, so any
document longer than that window is only partly represented by its vector.
Chunking removes that blind spot: each piece is embedded complete.

`semantic-text-splitter` does the splitting. It walks natural boundaries from
paragraphs down to sentences and words, takes the largest unit that still fits,
and merges neighbours back together while there is room. So the size is a ceiling
rather than a target: text is cut where it already divides, and a document under
the ceiling comes back untouched as a single piece. That is what keeps the rule
general. Nothing here is tuned to this corpus, and a larger corpus with longer
articles would be handled the same way.
"""

from semantic_text_splitter import TextSplitter

from supernatural_expert.embedding.encoder import load_tokenizer
from supernatural_expert.embedding.models import DEFAULT_MODEL, EmbeddingModel

# A widely used size for retrieval chunks, and independent of this corpus. Larger
# pieces average more topics into one vector and match everything weakly; smaller
# ones sharpen the vector but strand the sentence that gives it meaning. The
# model's own window caps this, whichever is smaller.
DEFAULT_CHUNK_TOKENS = 256

# Enough to carry a sentence across a boundary, so a fact split down the middle
# still appears whole in one piece.
DEFAULT_OVERLAP_TOKENS = 32


class Chunker:
    """Splits text to fit one embedding model's window."""

    def __init__(
        self,
        model: EmbeddingModel = DEFAULT_MODEL,
        target_tokens: int = DEFAULT_CHUNK_TOKENS,
        overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
    ) -> None:
        tokenizer = load_tokenizer(model)
        # The splitter counts the text alone, while the encoder later wraps every
        # piece in markers such as [CLS] and [SEP] that also occupy positions.
        # Asking the tokenizer how many it adds to an empty string keeps this
        # right for any model, instead of assuming the usual two.
        reserved = len(tokenizer.encode("").ids)
        self.capacity = min(target_tokens, model.max_tokens) - reserved
        if overlap_tokens >= self.capacity:
            raise ValueError(
                f"overlap_tokens={overlap_tokens} must be below the {self.capacity} "
                "token capacity, or pieces would repeat instead of advancing."
            )
        self.model = model
        self.overlap_tokens = overlap_tokens
        self._splitter = TextSplitter.from_huggingface_tokenizer(  # pyright: ignore[reportUnknownMemberType]
            tokenizer, self.capacity, overlap=overlap_tokens
        )

    def split(self, text: str) -> list[str]:
        """Return the pieces of `text`, in reading order.

        Text already within capacity comes back as one piece. Whitespace-only
        text yields nothing, so it never becomes an unsearchable empty unit.
        """
        return self._splitter.chunks(text)
