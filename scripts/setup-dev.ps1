# Prepares a fresh clone for local development on Windows.
# Run from the repository root: .\scripts\setup-dev.ps1
# Every step is safe to repeat.

$ErrorActionPreference = "Stop"

# Claude Code only discovers skills under .claude/skills, while Codex reads
# .agents/skills. A junction points one at the other so both tools share a
# single copy. Git cannot store a junction, so each clone recreates it.
if (Test-Path ".claude\skills") {
    Write-Host "Skipped the .claude\skills junction; it already exists."
} else {
    New-Item -ItemType Junction -Path ".claude\skills" -Target ".agents\skills" | Out-Null
    Write-Host "Created the .claude\skills junction."
}

# .env holds real credentials and is never committed.
if (Test-Path ".env") {
    Write-Host "Skipped .env; it already exists."
} else {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example. Add OPENAI_API_KEY; every other value already works."
}

uv sync

# This script stays offline and idempotent, so it prepares the host and stops
# there. Starting the database and loading the corpus need Docker running and
# reach the network, so they are left as explicit steps.
Write-Host ""
Write-Host "Setup complete. Next:"
Write-Host "  1. docker compose up -d --wait"
Write-Host "  2. uv run python -m supernatural_expert.ingestion --dry-run   # optional, writes data/corpus/*.json"
Write-Host "  3. uv run python -m supernatural_expert.ingestion             # loads 132 documents into PostgreSQL"
