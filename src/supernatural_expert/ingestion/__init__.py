"""Wikipedia to PostgreSQL ingestion. See docs/ingestion.md.

Importers reach for the module that owns what they need, such as
`supernatural_expert.ingestion.wikitext`. This package deliberately re-exports
nothing, so renaming a symbol touches only its own module and its callers.
"""
