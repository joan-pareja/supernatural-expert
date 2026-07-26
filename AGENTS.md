# Agent guide

> Keep this file short. It is routing and working guidance, not project design.

- Use `uv`; `pyproject.toml` and `uv.lock` are the dependency sources.
- Use Ruff for linting and formatting, and Pyright for type checking.
- Keep `[tool.pyright].include` directory-based so new files are checked
  automatically.
- Load settings with `dotenv_values` into a config object. Never call
  `load_dotenv` or read `os.environ`; the process environment stays untouched.
- Pass credentials and settings explicitly to every client. Name variables so
  implicit pickup cannot happen, such as `LOGFIRE_WRITE_TOKEN`, not
  `LOGFIRE_TOKEN`.
- Support Windows 10 with PowerShell and the Docker Compose reviewer flow.
- Read [Context](CONTEXT.md) and [Architecture](ARCHITECTURE.md), then open only
  the document that owns the part being changed.
- Keep one owner for each decision. Link to it instead of copying its text.
- Update `modified` when editing a knowledge note.
- Manage commits with the `wrap-up` skill, which owns the title and body rules
  and validates a title before it is used.
- Never print or commit secrets.
