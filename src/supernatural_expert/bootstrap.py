"""Loads the corpus and builds the search index when the database lacks them.

Run it from the repository root:

    uv run python -m supernatural_expert.bootstrap

Docker Compose runs this before the chat starts, which is what lets one command
be the whole of the setup. Each step is skipped when the database already holds
its result, so every start after the first costs two counting queries rather than
a fetch of Wikipedia and a re-encode of every search unit.

Nothing here is specific to a container. A contributor who has just started the
database gets the same two steps in the same order, which is why this is a module
rather than a line in a shell script.
"""

import sys
from typing import Any

from supernatural_expert.config import Settings, load_settings
from supernatural_expert.ingestion.documents import EXPECTED_EPISODE_COUNTS, SEASONS
from supernatural_expert.ingestion.pipeline import DATASET_NAME, DOCUMENT_TABLE
from supernatural_expert.ingestion.pipeline import main as load_corpus
from supernatural_expert.search.index import SCHEMA, UNIT_TABLE, connect
from supernatural_expert.search.index import main as build_index

CORPUS_TABLE = f"{DATASET_NAME}.{DOCUMENT_TABLE}"
INDEX_TABLE = f"{SCHEMA}.{UNIT_TABLE}"

# Every episode, plus one introduction per season. Ingestion refuses to load a
# partial corpus, so anything short of this is a run that never finished, and
# fetching the six seasons again is cheaper than serving half a knowledge base.
EXPECTED_DOCUMENTS = sum(EXPECTED_EPISODE_COUNTS.values()) + len(SEASONS)


def count_rows(settings: Settings, table: str) -> int | None:
    """Return how many rows a table holds, or None when it does not exist yet.

    The two table names are module constants rather than anything a caller
    supplies, which is why they are formatted into the second statement:
    `to_regclass` takes a name as a value, and `count(*)` cannot.
    """
    connection = connect(settings)
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT to_regclass(%s)", (table,))
            found: Any = cursor.fetchone()[0]
            if found is None:
                return None
            cursor.execute(f"SELECT count(*) FROM {table}")
            return int(cursor.fetchone()[0])
    finally:
        connection.close()


def plan(documents: int | None, units: int | None) -> tuple[bool, bool]:
    """Say whether the corpus needs loading and whether the index needs building.

    The two are decided together rather than one after the other, because a
    corpus that had to be loaded again replaces the documents the surviving units
    were built from, and an index describing documents that are gone is worse
    than no index at all.
    """
    load = documents != EXPECTED_DOCUMENTS
    return load, load or not units


def main() -> int:
    settings = load_settings()

    documents = count_rows(settings, CORPUS_TABLE)
    units = count_rows(settings, INDEX_TABLE)
    load, build = plan(documents, units)

    if load:
        found = documents if documents is not None else 0
        print(f"Corpus holds {found} of {EXPECTED_DOCUMENTS} documents. Loading it.")
        load_corpus([])
    else:
        print(f"Corpus holds {documents} documents. Skipping ingestion.")

    if build:
        build_index()
    else:
        print(f"Index holds {units} search units. Skipping the rebuild.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
