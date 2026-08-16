# Agent guide

> Keep this file short. It is the rule list and nothing else.
> [Development](docs/development.md) explains why these rules exist; do not
> repeat its reasoning here.

## Dependencies and tooling

- Use `uv`; `pyproject.toml` and `uv.lock` are the dependency sources. Never add
  `requirements.txt` or let `dlt init` create competing project files.
- Use Ruff for linting and formatting, and Pyright for type checking. `uv run
  pyright` is the authority; the editor runs its own checker against a cached
  environment, so reload the window after `uv add` rather than patching code to
  satisfy a stale diagnostic.
- Keep `[tool.pyright].include` directory-based so new files are checked
  automatically.
- Support Windows 10 with PowerShell and the Docker Compose reviewer flow.

## Running the code

- Run `.\scripts\setup-dev.ps1` first in a fresh clone. It creates `.env` from
  `.env.example`, installs the locked dependencies, downloads the pinned ONNX
  models into `models/`, and links the shared agent skills. Rerunning it is safe.
- Iterate with the app on the host and only the database in Docker, which is
  faster than rebuilding the image:

  ```powershell
  docker compose up -d --wait db
  uv run python -m supernatural_expert.bootstrap
  uv run streamlit run src/supernatural_expert/chat/app.py
  ```

- `bootstrap` loads the corpus and builds the index, skipping whichever the
  database already holds. It is the same step the container runs.
- Reload the corpus with `uv run python -m supernatural_expert.ingestion`, and
  add `--dry-run` to write one JSON file per season to `data/corpus/` without
  touching PostgreSQL. A run produces 132 documents or fails; `--help` lists the
  rest.
- Pass all four checks before committing: `uv run ruff check .`, `uv run ruff
  format .`, `uv run pyright`, and `uv run pytest -q`.

## Settings and secrets

- Load settings with `dotenv_values` into a config object. Never call
  `load_dotenv` or read `os.environ`; the process environment stays untouched.
- Pass credentials and settings explicitly to every client. Name variables so
  implicit pickup cannot happen, such as `LOGFIRE_WRITE_TOKEN`, not
  `LOGFIRE_TOKEN`.
- Never print or commit secrets.

## Documentation

- Read [Context](CONTEXT.md) and [Architecture](ARCHITECTURE.md), then open only
  the document that owns the part being changed.
- Keep one owner for each decision. Link to it instead of copying its text.
- Write notes in the indicative: "Optuna searches the parameters worth tuning",
  never "Use Optuna to search". The maintenance line under a title is the only
  exception, along with this file and [Development](docs/development.md).
- Start every note except `README.md`, `AGENTS.md`, and `LICENSE` with
  frontmatter carrying `type`, `status`, and `modified`.
- Update `modified` when editing a note. Read the clock at the moment of the
  edit and stamp that, in the maintainer's Europe/Madrid time. Never estimate,
  round to a tidy hour, or copy another note's value; a stamp in the future is
  always wrong. Ask if the real time cannot be read.
- Use `related` only for direct note links, and ordinary Markdown links in prose.

## Hosted instance

- The public chat runs on an Oracle Cloud VM, reached with `ssh -i
  ~/.ssh/oracle.key ubuntu@supernatural-expert.duckdns.org`. Address it by name,
  never by the IP behind it.
- The repository is cloned at `~/supernatural-expert` there, and `docker compose
  up -d` is the whole of the run. Pull before rebuilding; that clone is behind
  `main` whenever a commit has not reached it.
- Caddy runs on the host rather than in Compose. `deploy/Caddyfile` is what
  `/etc/caddy/Caddyfile` is copied from, so edit the repository and copy, never
  the other way round.
- Never write a key, a `.env`, or anything else carrying a secret into the
  repository.
- [Deployment](docs/deployment.md) owns the rest.

## Git

- Work on `main`. Branch only for speculative work that may be discarded, name
  it `<label>/<verb-led-name>`, and delete it once merged or dropped.
- Manage commits with the `wrap-up` skill, which owns the title and body rules
  and validates a title before it is used.
