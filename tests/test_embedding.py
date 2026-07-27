"""Tests for the local ONNX encoder and the chunker that feeds it.

The weights are downloaded rather than committed, so tests needing them skip when
they are absent. What they pin are the properties the rest of the system relies
on and that fail silently rather than loudly: vectors are unit length and the
declared width, padding never changes a result, a query is encoded as a query,
and no chunk is ever long enough for the encoder to clip it.
"""

import numpy as np
import pytest

from supernatural_expert.embedding.chunking import Chunker
from supernatural_expert.embedding.encoder import (
    EmbeddingModelNotDownloadedError,
    Encoder,
    load_tokenizer,
)
from supernatural_expert.embedding.models import (
    ALL_MINILM_L6_V2,
    BGE_SMALL_EN_V1_5,
    DEFAULT_MODEL,
    MODELS_DIR,
    EmbeddingModel,
)

ABSENT = EmbeddingModel(
    repository="Xenova/not-downloaded",
    revision="0000000",
    dimensions=384,
    max_tokens=256,
    pooling="mean",
)


def needs(model: EmbeddingModel) -> pytest.MarkDecorator:
    return pytest.mark.skipif(
        not (model.directory / "model.onnx").is_file(),
        reason="Run: uv run python -m supernatural_expert.embedding",
    )


downloaded = needs(DEFAULT_MODEL)


@pytest.fixture(scope="module")
def encoder() -> Encoder:
    """Loading the weights costs a second, so the whole module shares one."""
    return Encoder()


@pytest.fixture(scope="module")
def chunker() -> Chunker:
    return Chunker()


class TestEmbeddingModel:
    def test_the_directory_follows_the_repository_name(self) -> None:
        assert BGE_SMALL_EN_V1_5.directory == MODELS_DIR / "Xenova/bge-small-en-v1.5"

    @pytest.mark.parametrize("max_tokens", [0, -1, 513])
    def test_a_window_a_bert_encoder_cannot_serve_is_rejected(
        self, max_tokens: int
    ) -> None:
        with pytest.raises(ValueError, match="512 positions"):
            EmbeddingModel(
                repository="Xenova/bge-small-en-v1.5",
                revision="ea104da",
                dimensions=384,
                max_tokens=max_tokens,
                pooling="cls",
            )

    def test_the_retrieval_model_carries_a_query_marker(self) -> None:
        assert BGE_SMALL_EN_V1_5.query_prefix
        # The similarity model was never trained with one, so it must stay bare.
        assert ALL_MINILM_L6_V2.query_prefix == ""


class TestMissingWeights:
    def test_the_encoder_names_the_command_that_fixes_it(self) -> None:
        with pytest.raises(
            EmbeddingModelNotDownloadedError, match="python -m supernatural_expert"
        ):
            Encoder(ABSENT)

    def test_the_chunker_names_it_too(self) -> None:
        with pytest.raises(EmbeddingModelNotDownloadedError):
            Chunker(ABSENT)


@downloaded
class TestEncoding:
    def test_vectors_are_the_declared_width_and_unit_length(
        self, encoder: Encoder
    ) -> None:
        vectors = encoder.encode_documents(["Dean drives.", "Sam sees visions."])
        assert vectors.shape == (2, DEFAULT_MODEL.dimensions)
        assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0, atol=1e-5)

    def test_no_texts_gives_an_empty_matrix_of_the_right_width(
        self, encoder: Encoder
    ) -> None:
        assert encoder.encode_documents([]).shape == (0, DEFAULT_MODEL.dimensions)

    def test_a_long_neighbour_does_not_change_a_short_text(
        self, encoder: Encoder
    ) -> None:
        # Texts are padded to the longest in the call, so this one is padded far
        # further when it travels beside a long text. The mask is the only reason
        # its vector comes out the same, which makes this the test that fails if
        # pooling ever counts padding.
        alone = encoder.encode_documents(["Bobby calls."])[0]
        crowded = encoder.encode_documents(
            ["Bobby calls.", "The brothers argue. " * 60]
        )[0]
        assert np.allclose(alone, crowded, atol=1e-5)

    def test_a_query_encodes_to_one_row(self, encoder: Encoder) -> None:
        assert encoder.encode_query("What car?").shape == (DEFAULT_MODEL.dimensions,)

    def test_a_query_is_encoded_as_a_query_not_as_a_passage(
        self, encoder: Encoder
    ) -> None:
        question = "What car do the brothers drive?"
        as_query = encoder.encode_query(question)
        as_passage = encoder.encode_documents([question])[0]
        prefixed = encoder.encode_documents([DEFAULT_MODEL.query_prefix + question])[0]
        assert np.allclose(as_query, prefixed, atol=1e-5)
        assert not np.allclose(as_query, as_passage, atol=1e-3)

    def test_related_text_scores_above_unrelated_text(self, encoder: Encoder) -> None:
        query = encoder.encode_query("What car do the brothers drive?")
        related, unrelated = encoder.encode_documents(
            ["They drive a 1967 Chevrolet Impala.", "Sam studies law at Stanford."]
        )
        assert float(related @ query) > float(unrelated @ query)

    def test_long_text_is_cut_at_the_model_window_not_the_file_default(
        self, encoder: Encoder
    ) -> None:
        # The published tokenizer.json fixes truncation at 128 tokens; leaving it
        # alone would discard most of nearly every corpus document.
        assert encoder.token_count("wendigo " * 1000) == DEFAULT_MODEL.max_tokens


@needs(ALL_MINILM_L6_V2)
class TestMeanPooling:
    """The other pooling shape, to keep the encoder from becoming bge-only."""

    def test_a_mean_pooled_model_still_yields_unit_vectors(self) -> None:
        vectors = Encoder(ALL_MINILM_L6_V2).encode_documents(["A wendigo hunts."])
        assert vectors.shape == (1, ALL_MINILM_L6_V2.dimensions)
        assert np.allclose(np.linalg.norm(vectors, axis=1), 1.0, atol=1e-5)


@downloaded
class TestTokenizerLoading:
    def test_truncation_is_off_so_length_can_be_measured(self) -> None:
        # The chunker would otherwise measure every long document as one full
        # chunk and never split anything.
        tokenizer = load_tokenizer(DEFAULT_MODEL)
        assert len(tokenizer.encode("wendigo " * 1000).ids) > DEFAULT_MODEL.max_tokens


@downloaded
class TestChunking:
    def test_capacity_leaves_room_for_the_markers_the_encoder_adds(
        self, chunker: Chunker
    ) -> None:
        assert chunker.capacity == 254

    def test_the_model_window_caps_the_requested_size(self) -> None:
        # A target above what the model can read must not win.
        assert Chunker(ALL_MINILM_L6_V2, target_tokens=400).capacity == 254

    def test_text_within_capacity_is_left_whole(self, chunker: Chunker) -> None:
        text = "Sam and Dean investigate a haunting in Wisconsin."
        assert chunker.split(text) == [text]

    def test_long_text_becomes_several_pieces(self, chunker: Chunker) -> None:
        assert len(chunker.split("The brothers hunt a wendigo. " * 200)) > 1

    def test_no_piece_is_long_enough_for_the_encoder_to_clip_it(
        self, chunker: Chunker, encoder: Encoder
    ) -> None:
        # The invariant the whole capacity calculation exists to hold.
        pieces = chunker.split("Dean salts and burns the bones. " * 300)
        assert max(encoder.token_count(p) for p in pieces) <= DEFAULT_MODEL.max_tokens

    def test_blank_text_yields_no_pieces(self, chunker: Chunker) -> None:
        assert chunker.split("   \n\n  ") == []

    def test_overlap_must_leave_room_to_advance(self) -> None:
        with pytest.raises(ValueError, match="below the"):
            Chunker(DEFAULT_MODEL, target_tokens=64, overlap_tokens=64)
