"""Tests for the ONNX cross-encoder that reorders a shortlist.

The weights are downloaded rather than committed, so tests needing them skip when
they are absent. What they pin is that the pair reaches the model as a pair: a
cross-encoder fed the query and the passage as one undivided sequence still
returns plausible numbers, and only their ordering shows the mistake.
"""

import pytest

from supernatural_expert.embedding.encoder import ModelNotDownloadedError
from supernatural_expert.reranking.models import DEFAULT_RERANKER, RerankerModel
from supernatural_expert.reranking.reranker import Reranker

ABSENT = RerankerModel(
    repository="Xenova/not-downloaded", revision="0000000", max_tokens=512
)

downloaded = pytest.mark.skipif(
    not (DEFAULT_RERANKER.directory / "model.onnx").is_file(),
    reason="Run: uv run python -m supernatural_expert.reranking",
)


class TestModel:
    def test_the_window_covers_query_and_passage_together(self) -> None:
        assert DEFAULT_RERANKER.max_tokens == 512

    @pytest.mark.parametrize("max_tokens", [0, 513])
    def test_a_window_a_bert_encoder_cannot_hold_is_refused(
        self, max_tokens: int
    ) -> None:
        with pytest.raises(ValueError):
            RerankerModel(repository="x", revision="y", max_tokens=max_tokens)

    def test_the_missing_weights_name_the_command_that_fixes_it(self) -> None:
        with pytest.raises(
            ModelNotDownloadedError, match="python -m supernatural_expert.reranking"
        ):
            Reranker(ABSENT)


@downloaded
class TestScoring:
    def test_the_passage_answering_the_query_scores_highest(self) -> None:
        """The pair has to arrive as a pair, and only the order reveals it."""
        reranker = Reranker()
        passages = [
            "Berlin is well known for its museums.",
            "Berlin has a population of 3,520,031 registered inhabitants.",
            "New York City is the most populous city in the United States.",
        ]

        scores = reranker.score("How many people live in Berlin?", passages)

        assert scores.index(max(scores)) == 1

    def test_one_score_per_passage_in_the_order_given(self) -> None:
        reranker = Reranker()
        assert len(reranker.score("a query", ["one", "two", "three"])) == 3

    def test_nothing_to_score_runs_no_model(self) -> None:
        assert Reranker().score("a query", []) == []
