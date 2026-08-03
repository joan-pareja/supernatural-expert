"""Builds the searchable pieces of the corpus, with no database involved.

A search unit is one chunk of one document, carrying the vector that chunk
encodes to and enough of its document to answer with. Units are rebuildable from
corpus documents alone, so changing the chunk size or the encoder means running
this again rather than re-fetching anything from Wikipedia.

Document fields are copied onto every unit rather than joined back at query time.
The copies cost a few hundred kilobytes across the whole corpus and buy two
things: search reads one table, and the index cannot be left pointing at corpus
rows that a later dlt load replaced. See docs/data-model.md.

Nothing here opens a connection. Chunking and encoding are the expensive, testable
part of indexing, and keeping them separate from the write means they can be
exercised without PostgreSQL running.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from supernatural_expert.embedding.chunking import Chunker
from supernatural_expert.embedding.encoder import Encoder, Vectors
from supernatural_expert.ingestion.documents import CorpusDocument, DocumentType


class UnbuildableDocumentError(RuntimeError):
    """Raised when a document yields no unit and so could never be found."""


@dataclass(frozen=True, slots=True)
class SearchUnit:
    """One chunk of one document, ready to be written to the index.

    `unit_text` is what gets matched, both lexically and by vector. `content` is
    the document it came from, whole, and is what an answer is written from: a
    piece earns a document its place in the results, and the agent then reads the
    document. See docs/retrieval.md.
    """

    unit_id: str
    document_id: str
    # Position within the document, so pieces can be read back in order.
    unit_index: int
    unit_text: str
    embedding: Vectors

    # Copied from the document, for filtering, ranking, and citations.
    document_type: DocumentType
    season_number: int
    episode_number: int | None
    title: str
    content: str
    source_url: str


def build_units(
    documents: Sequence[CorpusDocument], chunker: Chunker, encoder: Encoder
) -> list[SearchUnit]:
    """Chunk and encode every document, in document order.

    The chunker and encoder are passed in rather than built here. Both are
    expensive to construct and both decide what the vectors mean, so the caller
    names them explicitly instead of inheriting a default it cannot see.

    Every chunk in the corpus is encoded in a single call. The tokenizer pads the
    batch to its longest member and the attention mask discards that padding, so
    the result does not depend on how the texts were grouped.
    """
    pieces: list[tuple[CorpusDocument, int, str]] = []
    for document in documents:
        chunks = chunker.split(document.content)
        if not chunks:
            raise UnbuildableDocumentError(
                f"{document.document_id} produced no search unit, so nothing could "
                "ever retrieve it."
            )
        pieces.extend((document, index, chunk) for index, chunk in enumerate(chunks))

    embeddings = encoder.encode_documents([chunk for _, _, chunk in pieces])

    return [
        SearchUnit(
            unit_id=f"{document.document_id}#{index:02d}",
            document_id=document.document_id,
            unit_index=index,
            unit_text=chunk,
            embedding=embeddings[row],
            document_type=document.document_type,
            season_number=document.season_number,
            episode_number=document.episode_number,
            title=document.title,
            content=document.content,
            source_url=document.source_url,
        )
        for row, (document, index, chunk) in enumerate(pieces)
    ]
