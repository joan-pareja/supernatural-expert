# Supernatural Expert

Ask questions about *Supernatural* seasons 1 to 6 and get an answer built from
Wikipedia, with the episodes it came from listed underneath. It will not tell you
anything past season 6, and it says so plainly when the corpus does not hold the
answer.

> The short entry point. [Journey](JOURNEY.md) is the long one, and the file to
> read if you read only one.

## Try it

You need Docker and an OpenAI API key. Nothing else: no Python to install, no
database to set up, no model files to fetch by hand.

```powershell
git clone https://github.com/joan-pareja/supernatural-expert
cd supernatural-expert
Copy-Item .env.example .env
```

Open `.env` and put your key on the `OPENAI_API_KEY=` line. Everything else in
that file already works, so leave it alone. Then start the whole thing:

```powershell
docker compose up
```

When the log says the app is running, open <http://127.0.0.1:8501>.

![The chat answering a question, with its source](docs/images/chat__question-and-citation.png)

### How long it takes

The first run does the slow work once and never again:

| | First run | Every run after |
|---|---|---|
| Downloading the base images | a few minutes, on your connection | skipped |
| Building the image | about 1½ minutes | skipped |
| Loading and indexing 132 documents | about 30 seconds | skipped |
| Starting the chat | seconds | seconds |

The two middle rows were measured on the maintainer's laptop. The download is the
part that varies, and it is the larger cost: PostgreSQL is a 1.4 GB image, and
the app image builds out to 3.2 GB once the Python dependencies and the two
models are in it. How long the setup takes depends on your machine and internet
connection.

Nothing in between needs you. The database starts, the app waits until it is
really answering, fetches the corpus from pinned Wikipedia revisions, builds the
search index, and serves the page. Later starts count two tables, find the work
already done, and go straight to the chat.

`docker compose down` stops everything. Add `-v` only if you want the corpus
deleted and loaded again next time.

### What it costs

Answering a question calls OpenAI, which costs money. Measured over the 223
questions behind the latest evaluation results, one costs under a tenth of a US
cent — roughly fifteen questions to the cent. A long conversation costs more per
answer than that, because each turn sends the ones before it again.

Nothing else costs anything. The two Logfire lines in `.env` can stay empty, and
the app then runs and sends no telemetry. Filling in a write token from a free
Logfire project turns the traces, cost figures, and dashboard on instead;
[Monitoring](docs/monitoring.md) gives the five steps.

## Read the Journey while it builds

**[Journey](JOURNEY.md)** is how this was built: what was tried, what it was
measured against, what the numbers said, and what got thrown away afterwards. It
is meant to be read start to finish, and it covers every part the course rubric
scores.

[Rubric](docs/rubric.md) is the checklist version — each criterion and where its
evidence lives — tracking the official
[LLM Zoomcamp project rubric](https://github.com/DataTalksClub/llm-zoomcamp/blob/main/project.md).

## What it does

- A chat page that answers one question at a time and shows the sources under
  every answer.
- Two kinds of search over the corpus at once: one matching words, one matching
  meaning. Their results are merged, then reordered by a model that reads each
  result against the question.
- Answers written by `gpt-5.6-luna` through Pydantic AI, citing the documents
  they rest on, refusing spoilers past season 6, and saying so rather than
  guessing when the corpus does not cover the question.
- A thumbs up or down on every answer.
- Traces, token usage, cost, judge verdicts, and ratings in one Logfire project,
  with a six-chart dashboard reading them in place.

The knowledge base is 132 documents covering every episode of seasons 1 to 6,
loaded from the Wikipedia API by a repeatable dlt pipeline. It is fixed rather
than configurable on purpose: a two-week project spends its time better on
retrieval, evaluation, and monitoring than on loading an arbitrary corpus at
runtime. See [Corpus](docs/corpus.md), [Ingestion](docs/ingestion.md), and
[Architecture](ARCHITECTURE.md).

## Working on the code

Contributors run the code on the host and keep only the database in Docker, which
is faster to iterate on than rebuilding an image:

```powershell
.\scripts\setup-dev.ps1
docker compose up -d --wait db
uv run python -m supernatural_expert.bootstrap
uv run streamlit run src/supernatural_expert/chat/app.py
```

`setup-dev.ps1` creates `.env` from `.env.example`, installs the locked
dependencies with `uv`, downloads the pinned ONNX models into `models/`, and
links the shared agent skills. Every step keeps what is already there, so the
script is safe to rerun. `bootstrap` is the same step the container runs: it
loads the corpus and builds the index unless the database already holds them.

Ingestion also runs on its own, and its dry run fetches and parses everything
without touching PostgreSQL, writing one JSON file per season to `data/corpus/`
so the result can be read first:

```powershell
uv run python -m supernatural_expert.ingestion --dry-run
uv run python -m supernatural_expert.ingestion
```

A run produces 132 corpus documents across seasons 1 through 6, and fails rather
than loading a partial corpus.

The checks that must pass: `uv run ruff check .`, `uv run ruff format .`,
`uv run pyright`, and `uv run pytest -q`. See
[Development](docs/development.md).

## Documentation map

Start with [Journey](JOURNEY.md). These are what it links into.

- [Scope](docs/scope.md): the problem and the boundary of the first release.
- [Architecture](ARCHITECTURE.md): the pieces and how they fit.
- [Corpus](docs/corpus.md): what the knowledge base contains.
- [Ingestion](docs/ingestion.md): how Wikipedia becomes corpus documents.
- [Data model](docs/data-model.md): the few stored concepts.
- [Retrieval](docs/retrieval.md): search, chunking, and reranking decisions.
- [Agent](docs/agent.md): how a question becomes an answer.
- [Chat](docs/chat.md): the Streamlit page and its feedback control.
- [Evaluation](docs/evaluation.md): how everything above was measured.
- [Monitoring](docs/monitoring.md): Logfire events, feedback, and the dashboard.
- [Rubric](docs/rubric.md): the course checklist and where each point is earned.
- [Development](docs/development.md): tools, commits, and Markdown rules.
- [Roadmap](ROADMAP.md): build order.
- [Context](CONTEXT.md): project-specific words.

## License

Project code is released under the [MIT License](LICENSE). Wikipedia text keeps
its own license and attribution requirements; see [NOTICE](NOTICE.md).
