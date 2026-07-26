---
type: reference
title: Development guide
description: Defines the agreed local tools, quality checks, branching, and note metadata.
status: approved
modified: 2026-07-26T22:45:00+02:00
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

[Architecture](../ARCHITECTURE.md) owns which libraries and models the
application uses, including the agent framework, the answer model, and how
embeddings run. Package choices belong beside the boundary they serve, not in a
second list here.

## Branching

Work on `main`. The project has one maintainer, no continuous integration gates,
and no pull request review, so a long-lived `dev` branch would add merge work
without adding isolation. Keeping `main` as the only permanent branch also keeps
the wrap-up skill in its trunk-only mode.

Create a short-lived `<label>/<verb-led-name>` branch only for speculative work
that may be discarded, such as a retrieval or chunking experiment. Delete it once
the result is merged or dropped.

## Commits

Use Conventional Commits. The `wrap-up` skill in `.agents/skills/wrap-up/` owns
the exact title and body rules and ships a validator that checks a title before
it is used. Restating those rules here would give them a second owner that can
drift from the one doing the checking.

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
