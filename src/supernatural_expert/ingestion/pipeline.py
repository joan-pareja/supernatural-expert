"""The dlt pipeline that loads corpus documents into PostgreSQL.

Run it from the repository root:

    uv run python -m supernatural_expert.ingestion --dry-run
    uv run python -m supernatural_expert.ingestion

The dry run writes one JSON file per season and touches no database, so the
parsed corpus can be read before anything is stored.
"""

import argparse
import json
from collections import Counter
from collections.abc import Iterator
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import dlt
from dlt.common.pipeline import LoadInfo
from dlt.destinations import postgres
from dlt.destinations.impl.postgres.configuration import PostgresCredentials

from supernatural_expert.config import REPOSITORY_ROOT, Settings, load_settings
from supernatural_expert.ingestion.documents import (
    EXPECTED_EPISODE_COUNTS,
    SEASONS,
    CorpusDocument,
    CorpusError,
    build_season_documents,
)
from supernatural_expert.ingestion.wikipedia import WikipediaClient

PIPELINE_NAME = "supernatural_corpus"
DATASET_NAME = "corpus"
DOCUMENT_TABLE = "corpus_documents"

# Keep dlt's working files beside the other tool caches instead of in ~/.dlt, so
# the repository stays self-contained and `.cache/` covers it in .gitignore.
PIPELINES_DIR = REPOSITORY_ROOT / ".cache" / "dlt"
DEFAULT_EXPORT_DIR = REPOSITORY_ROOT / "data" / "corpus"


def collect_documents(
    client: WikipediaClient, seasons: list[int], retrieved_at: datetime
) -> list[CorpusDocument]:
    """Fetch and validate every requested season, newest failure first."""
    documents: list[CorpusDocument] = []
    for season in seasons:
        season_documents = build_season_documents(client, season, retrieved_at)
        episodes = sum(1 for d in season_documents if d.document_type == "episode")
        print(f"Season {season}: {episodes} episodes and 1 introduction")
        documents.extend(season_documents)
    return documents


# dlt ships type hints whose overloads are only partially resolvable, so Pyright
# cannot narrow these three call sites. The ignores are per-symbol on purpose;
# turning the rule off project-wide would hide the same problem in our own code.
@dlt.resource(  # pyright: ignore[reportUnknownMemberType]
    name=DOCUMENT_TABLE,
    write_disposition="replace",
    primary_key="document_id",
)
def corpus_documents(documents: list[CorpusDocument]) -> Iterator[dict[str, Any]]:
    """Yield canonical corpus documents for dlt to load.

    Records are flat, so this produces one table and no child tables.

    `replace` matches the refresh policy: the corpus is static, and rerunning
    ingestion should rebuild the table rather than append a second copy.
    """
    for document in documents:
        yield document.as_record()


def build_destination(settings: Settings) -> Any:
    """Create the PostgreSQL destination from explicitly passed credentials.

    dlt would otherwise look for its own environment variables and
    `.dlt/secrets.toml`. Passing the credentials object closes that path.
    """
    postgres_settings = settings.postgres
    # A mapping, not a connection string: no URL-encoding traps for passwords,
    # and dlt redacts the password in logs and traces.
    credentials = PostgresCredentials(
        {
            "database": postgres_settings.database,
            "username": postgres_settings.username,
            "password": postgres_settings.password,
            "host": postgres_settings.host,
            "port": postgres_settings.port,
        }
    )
    return postgres(credentials=credentials)


def run_pipeline(settings: Settings, documents: list[CorpusDocument]) -> LoadInfo:
    """Load the documents into PostgreSQL and verify what landed."""
    pipeline = dlt.pipeline(
        pipeline_name=PIPELINE_NAME,
        destination=build_destination(settings),
        dataset_name=DATASET_NAME,
        pipelines_dir=str(PIPELINES_DIR),
        progress="log",
    )
    info = pipeline.run(  # pyright: ignore[reportUnknownMemberType]
        corpus_documents(documents)
    )

    with pipeline.sql_client() as sql_client:
        with sql_client.execute_query(
            f"SELECT COUNT(*) FROM {sql_client.make_qualified_table_name(DOCUMENT_TABLE)}"
        ) as cursor:
            row = cursor.fetchone()
    loaded = int(row[0]) if row else 0
    if loaded != len(documents):
        raise CorpusError(
            f"{DATASET_NAME}.{DOCUMENT_TABLE} holds {loaded} rows, "
            f"expected {len(documents)}."
        )
    print(f"Loaded {loaded} corpus documents into {DATASET_NAME}.{DOCUMENT_TABLE}.")
    return info


def export_documents(documents: list[CorpusDocument], output_dir: Path) -> None:
    """Write one JSON file per season for human inspection."""
    output_dir.mkdir(parents=True, exist_ok=True)
    by_season: dict[int, list[CorpusDocument]] = {}
    for document in documents:
        by_season.setdefault(document.season_number, []).append(document)

    for season, season_documents in sorted(by_season.items()):
        path = output_dir / f"season-{season:02d}.json"
        path.write_text(
            # ensure_ascii=False keeps em dashes and accents readable. These files
            # exist to be read; escaping every non-ASCII character defeats that.
            # It changes nothing that reaches PostgreSQL, which always gets the
            # real characters.
            json.dumps(
                [asdict(d) for d in season_documents],
                indent=2,
                default=str,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        print(f"Wrote {path.relative_to(REPOSITORY_ROOT)}")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="python -m supernatural_expert.ingestion",
        description="Load Supernatural seasons 1 to 6 from Wikipedia into PostgreSQL.",
    )
    parser.add_argument(
        "--season",
        type=int,
        action="append",
        choices=list(SEASONS),
        help="Ingest only this season. Repeatable. Defaults to all six.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Fetch, parse, and validate without connecting to PostgreSQL.",
    )
    parser.add_argument(
        "--export",
        action="store_true",
        help="Also write one JSON file per season. Implied by --dry-run.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=DEFAULT_EXPORT_DIR,
        help=f"Where exported JSON goes. Defaults to {DEFAULT_EXPORT_DIR}.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    seasons = sorted(set(args.season)) if args.season else list(SEASONS)
    settings = load_settings()

    client = WikipediaClient(settings.wikipedia_user_agent)
    retrieved_at = datetime.now(UTC)
    documents = collect_documents(client, seasons, retrieved_at)

    if seasons == list(SEASONS):
        # Every episode, plus one introduction per season.
        expected = sum(EXPECTED_EPISODE_COUNTS.values()) + len(SEASONS)
        if len(documents) != expected:
            raise CorpusError(
                f"Fetched {len(documents)} documents, expected {expected}."
            )

    if args.dry_run or args.export:
        export_documents(documents, args.output_dir)

    if args.dry_run:
        counts = Counter(d.content_source for d in documents)
        breakdown = ", ".join(
            f"{count} {source}" for source, count in sorted(counts.items())
        )
        print(
            f"Dry run: {len(documents)} corpus documents ({breakdown}). "
            "Nothing was written to PostgreSQL."
        )
        return 0

    run_pipeline(settings, documents)
    return 0
