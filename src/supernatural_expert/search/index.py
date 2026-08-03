"""Creates the search schema and fills it with search units.

Run it from the repository root, after ingestion has loaded the corpus:

    uv run python -m supernatural_expert.search

The index lives in its own `search` schema rather than beside the corpus. dlt
owns the `corpus` dataset and may drop and recreate it on a refresh, which would
take a co-located table with it. Separate schemas keep each owner's reach clear.

Building always drops and recreates the table. Search units are derived data, and
rebuilding all of them takes about twenty seconds, so there is no incremental
path to get wrong. Chunking or encoder changes are a rerun, not a migration.
"""

from dataclasses import fields
from typing import Any

import psycopg2  # pyright: ignore[reportMissingTypeStubs]
from psycopg2.extras import (  # pyright: ignore[reportMissingTypeStubs]
    execute_values,  # pyright: ignore[reportUnknownVariableType]
)

from supernatural_expert.config import Settings, load_settings
from supernatural_expert.embedding.chunking import Chunker
from supernatural_expert.embedding.encoder import Encoder
from supernatural_expert.embedding.models import DEFAULT_MODEL, EmbeddingModel
from supernatural_expert.ingestion.documents import CorpusDocument
from supernatural_expert.ingestion.pipeline import DATASET_NAME, DOCUMENT_TABLE
from supernatural_expert.search.units import SearchUnit, build_units

SCHEMA = "search"
UNIT_TABLE = "search_units"


class EmptyCorpusError(RuntimeError):
    """Raised when there is nothing to index because ingestion has not run."""


# Every column a unit is written to, in the order the insert supplies them. The
# generated tsvector is deliberately absent: PostgreSQL computes it.
UNIT_COLUMNS = (
    "unit_id",
    "document_id",
    "unit_index",
    "unit_text",
    "embedding",
    "document_type",
    "season_number",
    "episode_number",
    "title",
    "content",
    "source_url",
)

# Weight A outranks B in ts_rank by default, 1.0 against 0.4, so a title match is
# worth more than a body match without any tuned number. Assigning the weights in
# a stored generated column means it is computed once per unit at build time
# rather than per query, and no caller can forget to apply it.
LEXEME_EXPRESSION = """
    setweight(to_tsvector('english', title), 'A') ||
    setweight(to_tsvector('english', unit_text), 'B')
"""


def connect(settings: Settings) -> Any:
    """Open a connection with credentials passed explicitly.

    psycopg2 would otherwise fall back to PGHOST, PGPASSWORD and the rest of
    libpq's environment variables. Naming every parameter closes that path, the
    same way the dlt destination does.
    """
    postgres = settings.postgres
    return psycopg2.connect(  # pyright: ignore[reportUnknownMemberType]
        host=postgres.host,
        port=postgres.port,
        dbname=postgres.database,
        user=postgres.username,
        password=postgres.password,
    )


def create_table_sql(model: EmbeddingModel = DEFAULT_MODEL) -> str:
    """Return the DDL that builds one empty index.

    The vector width comes from the model rather than a literal, so swapping
    encoders cannot leave a column that silently rejects every row.
    """
    table = f"{SCHEMA}.{UNIT_TABLE}"
    return f"""
        CREATE SCHEMA IF NOT EXISTS {SCHEMA};

        DROP TABLE IF EXISTS {table};

        CREATE TABLE {table} (
            unit_id text PRIMARY KEY,
            document_id text NOT NULL,
            unit_index integer NOT NULL,
            unit_text text NOT NULL,
            embedding vector({model.dimensions}) NOT NULL,
            document_type text NOT NULL,
            season_number integer NOT NULL,
            episode_number integer,
            title text NOT NULL,
            content text NOT NULL,
            source_url text NOT NULL,
            lexemes tsvector GENERATED ALWAYS AS ({LEXEME_EXPRESSION}) STORED
        );

        CREATE INDEX {UNIT_TABLE}_lexemes_idx ON {table} USING gin (lexemes);

        -- Filters run against these on every path, and the table is small enough
        -- that this is the only other indexing it needs. Vector search stays an
        -- exact sequential scan; see docs/data-model.md.
        CREATE INDEX {UNIT_TABLE}_document_idx ON {table} (document_id);
        CREATE INDEX {UNIT_TABLE}_season_idx ON {table} (season_number);
    """


def to_pgvector(values: Any) -> str:
    """Render one embedding as the text literal pgvector parses.

    Sending text avoids a second Postgres adapter package for one column. The
    values are float32, whose seven significant digits survive this exactly.
    """
    return "[" + ",".join(f"{float(value):.7g}" for value in values) + "]"


def read_corpus_documents(connection: Any) -> list[CorpusDocument]:
    """Load every corpus document dlt wrote, in document order.

    Columns are taken from the dataclass, so a field added to `CorpusDocument`
    fails loudly here instead of arriving as a silently missing value.
    """
    names = [field.name for field in fields(CorpusDocument)]
    with connection.cursor() as cursor:
        cursor.execute(
            f"SELECT {', '.join(names)} FROM {DATASET_NAME}.{DOCUMENT_TABLE} "
            "ORDER BY document_id"
        )
        rows = cursor.fetchall()
    return [CorpusDocument(*row) for row in rows]


def write_units(connection: Any, units: list[SearchUnit]) -> None:
    """Insert every unit in one round trip."""
    rows = [
        (
            unit.unit_id,
            unit.document_id,
            unit.unit_index,
            unit.unit_text,
            to_pgvector(unit.embedding),
            unit.document_type,
            unit.season_number,
            unit.episode_number,
            unit.title,
            unit.content,
            unit.source_url,
        )
        for unit in units
    ]
    with connection.cursor() as cursor:
        execute_values(
            cursor,
            f"INSERT INTO {SCHEMA}.{UNIT_TABLE} ({', '.join(UNIT_COLUMNS)}) VALUES %s",
            rows,
        )


def build_index(settings: Settings) -> int:
    """Rebuild the whole index from the corpus and return the unit count."""
    chunker = Chunker()
    encoder = Encoder()

    # psycopg2's connection context manager ends the transaction but leaves the
    # socket open, so closing is explicit here.
    connection = connect(settings)
    try:
        documents = read_corpus_documents(connection)
        if not documents:
            raise EmptyCorpusError(
                f"{DATASET_NAME}.{DOCUMENT_TABLE} is empty. "
                "Run: uv run python -m supernatural_expert.ingestion"
            )

        units = build_units(documents, chunker, encoder)

        with connection.cursor() as cursor:
            cursor.execute(create_table_sql(encoder.model))
        write_units(connection, units)
        # PostgreSQL makes DDL transactional, so the drop, the create, and every
        # row commit together. A failed rebuild leaves the previous index intact
        # rather than an empty table.
        connection.commit()
    finally:
        connection.close()

    return len(units)


def main() -> int:
    settings = load_settings()
    count = build_index(settings)
    print(f"Indexed {count} search units into {SCHEMA}.{UNIT_TABLE}.")
    return 0
