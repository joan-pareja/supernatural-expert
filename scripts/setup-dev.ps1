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
    Write-Host "Created .env from .env.example. Fill in OPENAI_API_KEY and the Logfire tokens."
}

uv sync

Write-Host ""
Write-Host "Setup complete. Start the database with: docker compose up -d --wait"
