-- Runs once, when the database volume is first created.
-- pgvector stores the local ONNX embeddings used by vector search.
CREATE EXTENSION IF NOT EXISTS vector;

-- pg_search supplies BM25 lexical ranking. CASCADE would pull pgvector in on
-- its own, since pg_search depends on it; both are named anyway so the reason
-- each one is here stays readable.
CREATE EXTENSION IF NOT EXISTS pg_search;
