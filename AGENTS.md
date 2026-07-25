# Agent guide

> Keep this file short. It is routing and working guidance, not project design.

- Use `uv`; `pyproject.toml` and `uv.lock` are the dependency sources.
- Use Ruff for linting and formatting, and Pyright for type checking.
- Keep `[tool.pyright].include` directory-based so new files are checked
  automatically.
- Support Windows 10 with PowerShell and the Docker Compose reviewer flow.
- Read [Context](CONTEXT.md) and [Architecture](ARCHITECTURE.md), then open only
  the document that owns the part being changed.
- Keep one owner for each decision. Link to it instead of copying its text.
- Update `modified` when editing a knowledge note.
- Use Conventional Commit titles with a lowercase type and a lowercase,
  imperative summary of at most 70 characters and no final period. Use
  capitalized, verb-led, period-terminated body bullets.
- Never print or commit secrets.
