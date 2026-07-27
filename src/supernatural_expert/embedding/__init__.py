"""Local ONNX sentence embeddings. See docs/retrieval.md.

Importers reach for the module that owns what they need, such as
`supernatural_expert.embedding.encoder`. This package deliberately re-exports
nothing, so renaming a symbol touches only its own module and its callers.
"""
