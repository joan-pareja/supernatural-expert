# Supernatural Expert

Ask spoiler-safe questions about *Supernatural* seasons 1 through 6. The app will
retrieve episode facts from a fixed English Wikipedia corpus, then use an LLM to
answer with source links.

> Keep this file as the short entry point for people who want to understand,
> run, or review the project.

## Why this project is narrow

The first idea was a configurable movie-and-TV expert. That would spend too much
of a two-week project choosing and loading a new corpus at runtime. A fixed
*Supernatural* expert keeps the hard work on retrieval, evaluation, monitoring,
and reproducibility.

## What it does

- Chat through Streamlit.
- Search episode information with PostgreSQL text and vector search.
- Combine both result lists with reciprocal rank fusion (RRF), then reorder them
  with a cross-encoder that scores each result against the question.
- Answer with `gpt-5.6-luna` through Pydantic AI, citing the documents used.
- Refuse spoilers beyond Season 6 and answers unsupported by the corpus.
- Collect thumbs-up and thumbs-down feedback.
- Send every run, judge result, and rating to one Logfire project.

All of the above runs today. The monitoring charts over that Logfire data are the
piece still being built.

The corpus is loaded from the Wikipedia Action API by a repeatable dlt pipeline.
No web pages, raw API archives, or DuckDB landing database are part of the
runtime design. See [Corpus](docs/corpus.md), [Ingestion](docs/ingestion.md), and
[Architecture](ARCHITECTURE.md).

## Course rubric

The plan covers all nine two-point project sections: problem, retrieval, two
forms of evaluation, interface, ingestion, monitoring, containerization, and
reproducibility. Hybrid search, a cross-encoder reranker, and the agent's own
query rewriting are each measured against the ground truth and kept, which takes
three best-practice points. Cloud deployment is declined, for reasons the linked
documents give.

**Start with [Journey](JOURNEY.md)** for what was built, what it was measured
against, and what each decision was worth. The exact checklist and evidence
locations live in [Rubric](docs/rubric.md), which tracks the official
[LLM Zoomcamp project rubric](https://github.com/DataTalksClub/llm-zoomcamp/blob/main/project.md).

## Running the project

**The goal is one command and one secret: `docker compose up` with an
`OPENAI_API_KEY`.** Nothing else should be a prerequisite. The embedding model is
baked into the image rather than fetched by the reviewer, the corpus loads
itself, and every other credential is optional. Steps that do not yet meet that
bar are being worked toward it, not around it.

The application is not built yet, but the database it will use already runs
locally, and contributors work against the host rather than the image. From the
repository root on Windows:

```powershell
.\scripts\setup-dev.ps1
docker compose up -d --wait
```

`setup-dev.ps1` creates `.env` from `.env.example`, installs the locked
dependencies with `uv`, downloads the pinned ONNX models into `models/`, and
links the shared agent skills. Every step keeps what is already there, so the
script is safe to rerun. Stop the database with `docker compose down`; adding
`-v` also deletes its data.

Two models are fetched rather than committed: the 128 MB encoder that indexes and
searches, and the 91 MB cross-encoder that reorders what search returns. Running
`uv run python -m supernatural_expert.embedding` and `uv run python -m
supernatural_expert.reranking` again is how you restore them.

**`OPENAI_API_KEY` is the only value you must supply.** Everything else in
`.env.example` already works. The two Logfire tokens are optional: without them
the app runs and sends no telemetry, and with them it sends to your own Logfire
project so you can reproduce the monitoring views. See
[Monitoring](docs/monitoring.md).

Then load the corpus. The dry run fetches and parses everything without touching
PostgreSQL, writing one JSON file per season to `data/corpus/` so the result can
be read first:

```powershell
uv run python -m supernatural_expert.ingestion --dry-run
uv run python -m supernatural_expert.ingestion
```

A run produces 132 corpus documents across seasons 1 through 6, and fails
rather than loading a partial corpus.

The final local setup will use Docker Compose for the app and PostgreSQL. Docker
will provide all software dependencies. OpenAI usage may cost money; the Logfire
free tier does not.

Private Logfire access is not part of the handoff. The charts are drawn in
Logfire over the spans the app already sends, so the repository carries the
dashboard definition and screenshots, and the steps to point your own Logfire
project at the app and watch it fill up.

## Documentation map

- [Journey](JOURNEY.md): how the project got here, and what each turn was worth.
- [Scope](docs/scope.md): the problem and the boundary of the first release.
- [Corpus](docs/corpus.md): what the knowledge base contains.
- [Ingestion](docs/ingestion.md): how Wikipedia becomes corpus documents.
- [Data model](docs/data-model.md): the few stored concepts.
- [Retrieval](docs/retrieval.md): search and chunking decisions.
- [Evaluation](docs/evaluation.md): offline and online quality checks.
- [Monitoring](docs/monitoring.md): Logfire events and dashboard charts.
- [Development](docs/development.md): tools, commits, and Markdown rules.
- [Roadmap](ROADMAP.md): build order and open decisions.
- [Context](CONTEXT.md): project-specific words.

## License

Project code is released under the [MIT License](LICENSE). Wikipedia text keeps
its own license and attribution requirements; see [NOTICE](NOTICE.md).
