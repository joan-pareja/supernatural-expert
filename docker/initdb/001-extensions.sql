-- Runs once, when the database volume is first created.
-- pgvector stores the local ONNX embeddings used by vector search.
CREATE EXTENSION IF NOT EXISTS vector;
