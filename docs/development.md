---
type: reference
title: Development guide
description: Defines the agreed local tools, quality checks, commit style, and note metadata.
status: draft
modified: 2026-07-25T22:11:40+02:00
tags:
- development
- tooling
- documentation
related:
- ../AGENTS.md
- ../README.md
---

# Development guide

> Keep repository-wide working rules here. Put product and architecture choices
> in their own documents.

## Tooling

- Python package and dependency manager: `uv`.
- Project and lock files: `pyproject.toml` and `uv.lock`.
- One-off command runner: `uvx`, not a second package manager.
- Linting and formatting: Ruff.
- Type checking: Pyright.
- Local delivery: Docker Compose.
- Supported developer host: Windows 10 with PowerShell.

Do not add `requirements.txt` or let `dlt init` create competing project files.
The Docker image installs locked dependencies, so reviewers do not need `uv` on
their host.

`[tool.pyright].include` lists directories, not single files, so new Python files
and notebooks are type checked without editing configuration. Exact test and run
commands will be documented only after they exist and have been checked.

## Agent skills

Shared agent skills live in `.agents/skills/`, which Codex reads directly. Claude
Code only discovers skills under `.claude/skills/`, so that path is a directory
junction to `.agents/skills/`. Recreate it once per clone from the repository
root:

```powershell
New-Item -ItemType Junction -Path .claude\skills -Target .agents\skills
```

A junction avoids symlinks because unprivileged symlink creation needs more than
Developer Mode on Windows, while a junction needs no elevation. Git does not
understand junctions and would commit a second copy of every skill, so
`.claude/skills/` is ignored. Other `.claude` contents, such as hooks and
settings, stay tracked.

## Model tools

Use Pydantic AI for the agent and typed tool boundaries. The default answer model
is [`gpt-5.4-mini`](https://developers.openai.com/api/docs/models/gpt-5.4-mini).
Use a local CPU ONNX model for embeddings if the selected model passes the first
retrieval evaluation.

## Commits

Use Conventional Commits. Both the type and the imperative summary are
lowercase, and the summary takes no final period, such as
`docs: capture project design`. Keep the full title at 70 characters or fewer.
When a body helps, use capitalized, verb-led bullets that end with periods.

## Markdown metadata

Maintained knowledge notes use a local, OKF-friendly YAML frontmatter profile
that also works with Obsidian Properties.

- Every non-reserved Markdown note starts with parseable frontmatter.
- `type`, `status`, and `modified` are required.
- `status: draft` means the user has not approved the note; `approved` means the
  user has validated it.
- `modified` uses `YYYY-MM-DDTHH:mm:ss+HH:MM` in Europe/Madrid and changes with
  every content or metadata edit.
- Use `title`, `description`, and short lowercase `tags` when helpful.
- Use `related` only for direct note links.
- Use normal Markdown links in prose; do not mirror every link in `related`.
- `README.md`, `AGENTS.md`, and `LICENSE` are reserved entry files and are exempt.

Each note starts with one short maintenance line below its title. That line says
what belongs in the file and helps future edits stay focused.

References: [OKF v0.1](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)
and [Obsidian Properties](https://help.obsidian.md/properties).
