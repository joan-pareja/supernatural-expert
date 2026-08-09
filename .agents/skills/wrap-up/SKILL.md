---
name: wrap-up
description: Manage the branch for current repository work and draft an evidence-based Conventional Commit title and body. Use only when the user explicitly invokes this skill to wrap up or asks for branch and commit-message help; never stage, commit, push, update worklogs, or write memory summaries.
---

# Wrap Up

Manage the branch, then draft the commit message. Do not modify project files, stage changes, commit, push, update a worklog, or write a memory summary. Creating or switching a branch after user confirmation is the only permitted repository mutation.

## Manage the branch

1. Inspect the current branch, all local branches, all non-symbolic remote-tracking branches, and `git status --short`. Count staged, unstaged, and untracked files as work to commit.
2. If the current branch is detached, unknown, or unavailable, explain the problem and pause.
3. Normalize remote branch names by removing the remote prefix and ignore remote `HEAD` pointers.
4. If the only normalized branch is `main` or `master`, treat the repository as trunk-only. Stay on that branch, state that no working branch is required, and continue.
5. If `dev` or `develop` exists locally or remotely, treat `main`, `master`, `dev`, and `develop` as protected workflow branches:
   - If the current branch is protected and the worktree has changes, inspect the changes enough to identify one coherent unit, suggest one compliant working branch, and ask: `You are on <current>. Suggested branch: <suggested>. Switch?`
   - If the user confirms, verify the name is unused, run `git switch -c <suggested>`, and confirm the switch.
   - If the user declines, continue on the current branch without asking them to create anything manually.
   - If the current branch is already a compliant working branch, keep it.
6. If the branch set fits neither model, inspect recent branch naming and repository guidance. If the intended branching model remains unclear, ask one focused question instead of guessing.

Use `<label>/<surface?>/<verb-led-name>` for a suggested branch:

- Choose `feature` for a new capability, `bugfix` for a defect fix, `chore` for maintenance or tooling, and `refactor` for a behavior-preserving restructure.
- Include a lowercase surface only when repository history establishes stable surfaces or it materially disambiguates the work. Otherwise omit it.
- Write the final segment as a concise, imperative, kebab-case action phrase.
- Do not add ticket IDs, usernames, or tool prefixes unless repository history or explicit user guidance requires them.
- If the proposed name already exists locally or remotely, propose a more specific compliant name; never overwrite or force-move an existing branch.

## Establish the commit set

1. Use an explicitly named revision range or file set when the user provides one.
2. Otherwise, inspect `git status --short`, the staged and unstaged stats, name-status output, and full diffs.
3. Prefer the staged set when it is non-empty; otherwise use all current tracked and untracked changes.
4. Inspect relevant untracked files because ordinary diffs omit their content.
5. If staged and unstaged work materially diverge, or the changes contain unrelated concerns, stop and ask which coherent set the message should cover.

## Rebuild the evidence

- Treat the selected diff and files as the source of truth for what changed.
- Use the conversation and operator feedback to recover intent, motivation, and corrections, but do not claim changes absent from the commit set.
- After context compaction, reconstruct coverage from Git, changed files, relevant tests, and project documentation instead of trusting a lossy chat summary.
- Inspect recent non-merge commit titles and bodies, including history for the touched paths, to match the repository's language and established style.
- Ask one focused question when important intent remains unclear; never invent rationale, validation, issue references, breaking changes, or co-authors.

## Write the title

Use `type[(scope)][!]: summary`.

- Pick the narrowest accurate type: `feat`, `fix`, `refactor`, `perf`, `docs`, `test`, `build`, `ci`, `style`, `chore`, or `revert`. Use `feat` and `fix`, not `feature` or `bugfix`.
- Map working-branch labels to commit types: `feature` to `feat`, `bugfix` to `fix`, `chore` to `chore`, and `refactor` to `refactor`. If the branch label conflicts with the selected diff, resolve the branch or commit scope instead of forcing an inaccurate type.
- Add a lowercase scope only when it names a stable, useful codebase surface already supported by the repository or clearly established by the change. Omit it rather than inventing a one-off scope.
- Use `!` only for a verified breaking change.
- Write the summary as a lowercase, imperative, verb-led phrase with no final period.
- Keep the complete title at 70 characters or fewer, counting the type, scope, `!`, colon, spaces, and summary. This is an absolute limit with no exceptions, even when repository history contains longer titles.
- Shorten the summary, use a more concise accurate verb, or omit an optional scope until the title fits. Never return a title over 70 characters.
- Run `uv run python <skill-dir>/scripts/validate_commit_title.py "<title>"` before returning the message. Revise and rerun until it succeeds.

## Write the body

- Omit the body only when the title fully captures a trivial, coherent change.
- Write a log of what changed, not an argument for it. The body is scanned by someone asking what landed here.
- Write one bullet per distinct change, and keep each bullet to one sentence. A bullet needing a second sentence is either two changes or one change over-explained.
- Cover every distinct change once: behavior, contract or schema, configuration, migration or compatibility effect, test or documentation change, dependency or generated artifact, and operator-requested correction. Completeness means no change is missing, not that each is argued.
- Consolidate mechanical churn and closely related artifacts instead of listing every file.
- State why only when the diff cannot show it and no other artifact records it, and then in one clause of the bullet it belongs to. Most changes need none.
- Name the owning document instead of restating it when the commit adds or edits a note that carries the reasoning. Repeating it copies text that already has an owner.
- Use verb-led bullets for a multi-part change. Capitalize each complete bullet sentence and end it with a period unless repository history clearly follows another style.
- Keep each body bullet on one physical line; do not hard-wrap bullets.
- Do not repeat the title, replay the conversation, narrate Git commands, or pad the body with generic claims.
- Do not stack subordinate clauses, contrast what was done against what was not, or write a sentence whose subject is a design principle. Those belong in the notes the repository keeps.
- Do not include pull-request numbers.
- Mention validation only when it materially helps and was actually run.
- Add Conventional Commit footers, including `BREAKING CHANGE:`, only when verified and relevant.

## Check and return

Verify that the title and body cover the entire selected commit set without describing unrelated or absent work. If the set cannot be explained as one coherent commit, recommend a split instead of hiding it under a broad title.

Return one copy-paste-ready fenced text block containing only the title, a blank line, and the body when needed. Do not print Git commands.
