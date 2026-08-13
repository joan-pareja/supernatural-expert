"""Tests for the decision the container makes before the chat starts.

No database is touched. What these pin is when work is repeated and when it is
skipped, because both mistakes are expensive in opposite directions: a needless
rebuild costs a reviewer a fetch of Wikipedia on every restart, and a skipped one
serves an index describing documents that are no longer there.
"""

from supernatural_expert.bootstrap import EXPECTED_DOCUMENTS, plan


class TestPlan:
    def test_a_loaded_corpus_and_a_filled_index_leave_nothing_to_do(self) -> None:
        assert plan(EXPECTED_DOCUMENTS, 500) == (False, False)

    def test_an_empty_database_loads_and_indexes(self) -> None:
        assert plan(None, None) == (True, True)

    def test_a_corpus_that_stopped_part_way_is_loaded_again(self) -> None:
        assert plan(EXPECTED_DOCUMENTS - 1, None) == (True, True)

    def test_a_loaded_corpus_with_no_index_is_only_indexed(self) -> None:
        assert plan(EXPECTED_DOCUMENTS, None) == (False, True)
        assert plan(EXPECTED_DOCUMENTS, 0) == (False, True)

    def test_reloading_the_corpus_rebuilds_units_that_survived_it(self) -> None:
        # The units are there, but they describe the documents the reload
        # replaced, so keeping them would search a corpus that is gone.
        assert plan(0, 500) == (True, True)

    def test_the_expected_count_is_the_whole_corpus(self) -> None:
        assert EXPECTED_DOCUMENTS == 132
