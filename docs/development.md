---
type: reference
title: Development guide
description: Explains the local tooling, branching, and documentation choices and why they were made.
status: approved
modified: 2026-07-27T00:31:00+02:00
tags:
- development
- tooling
- documentation
related:
- ../AGENTS.md
- ../README.md
---

# Development guide

> Keep the reasoning behind repository-wide working choices here.
> [AGENTS.md](../AGENTS.md) states the rules themselves. Writing a rule in both
> places would give it two owners that can disagree.

## Tooling

- Python package and dependency manager: `uv`.
- Project and lock files: `pyproject.toml` and `uv.lock`.
- One-off command runner: `uvx`, not a second package manager.
- Linting and formatting: Ruff.
- Type checking: Pyright.
- Local delivery: Docker Compose.
- Supported developer host: Windows 10 with PowerShell.

One manager owns dependencies. A `requirements.txt` or a `dlt init` scaffold
would become a second source of truth that drifts from the lock file, and the
drift only shows up on someone else's machine. The Docker image installs those
locked dependencies, so a reviewer needs no `uv` on their host.

Pyright runs in strict mode over directories rather than a list of files, so a
new module is checked the moment it exists instead of when someone remembers to
register it. Where a third-party package ships incomplete types, the fix is a
narrow per-call ignore rather than relaxing the setting for the whole project.

## Agent skills

Shared agent skills live in `.agents/skills/`, which Codex reads directly. Claude
Code only discovers skills under `.claude/skills/`, so that path is a directory
junction to `.agents/skills/` and `scripts/setup-dev.ps1` recreates it in each
clone.

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

Work happens on `main`. The project has one maintainer, no continuous
integration gates, and no pull request review, so a long-lived `dev` branch would
add merge work without adding isolation. Keeping `main` as the only permanent
branch also keeps the wrap-up skill in its trunk-only mode.

Speculative work that may be discarded, such as a retrieval or chunking
experiment, is the one case that earns a short-lived branch.

## Commits

Commits follow Conventional Commits. The `wrap-up` skill in
`.agents/skills/wrap-up/` owns the exact title and body rules and ships a
validator that checks a title before it is used. Restating those rules here would
give them a second owner that can drift from the one doing the checking.

## Markdown notes

Maintained knowledge notes use a local, OKF-friendly YAML frontmatter profile
that also works with Obsidian Properties. `status` records whether the
maintainer has approved a note, which is what separates a draft opinion from a
settled decision. `modified` is a real timestamp rather than a tidy one, because
a stamp that was guessed cannot answer the only question it exists for: whether
this note is older than the code it describes.

Each note opens with one short maintenance line below its title, saying what
belongs in the file. It is the one piece of a note addressed to whoever edits it
next, which is why it is also the one piece written as an instruction.

Everything else is written in the indicative, describing what this project does
and why. A reviewer reading these notes is trying to follow reasoning, not
execute a procedure, and instructions phrased at them also read as commitments
the code may no longer honour. `README.md` and `AGENTS.md` are exempt: one
welcomes a reader, the other exists to instruct.

References: [OKF v0.1](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md)
and [Obsidian Properties](https://help.obsidian.md/properties).
