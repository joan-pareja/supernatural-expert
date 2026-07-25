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

## Planned experience

- Chat through Streamlit.
- Search episode information with PostgreSQL text and vector search.
- Combine both result lists with reciprocal rank fusion (RRF).
- Answer with `gpt-5.4-mini` through Pydantic AI.
- Refuse spoilers beyond Season 6 and answers unsupported by the corpus.
- Collect thumbs-up and thumbs-down feedback.
- Show evaluation and monitoring results from one Logfire data source.

The corpus is loaded from the Wikipedia Action API by a repeatable dlt pipeline.
No web pages, raw API archives, or DuckDB landing database are part of the
runtime design. See [Corpus](docs/corpus.md), [Ingestion](docs/ingestion.md), and
[Architecture](ARCHITECTURE.md).

## Course rubric

The plan covers all nine two-point project sections: problem, retrieval, two
forms of evaluation, interface, ingestion, monitoring, containerization, and
reproducibility. Hybrid search is also planned. A separate reranker and query
rewriting remain open work for the other two best-practice points. Cloud
deployment is not planned.

The exact checklist and evidence locations live in [Rubric](docs/rubric.md). It
tracks the official [LLM Zoomcamp project rubric](https://github.com/DataTalksClub/llm-zoomcamp/blob/main/project.md).

## Running the project

This repository currently holds the agreed design. Working Docker commands will
be added with the application.

The final local setup will use Docker Compose for the app and PostgreSQL. Docker
will provide all software dependencies. A reviewer will supply
`OPENAI_API_KEY`; OpenAI usage may cost money. Reproducing fresh monitoring data
will also require credentials for the reviewer's own Logfire project.

Private Logfire access is not part of the handoff. The public repository will
show the dashboard code, its queries, and screenshots with at least five charts.

## Documentation map

- [Scope](docs/scope.md): the problem and the boundary of the first release.
- [Corpus](docs/corpus.md): what the knowledge base contains.
- [Ingestion](docs/ingestion.md): how Wikipedia becomes episode documents.
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
