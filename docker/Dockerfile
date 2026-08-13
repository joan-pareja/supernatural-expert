# The chat and everything it runs on, so a reviewer supplies one secret and runs
# one command. The two ONNX models are baked in rather than fetched at start:
# they are pinned by revision and weigh 220 MB, and a first run should not wait
# on Hugging Face or fail when it is down.

# Pinned to the version the lock file was resolved with, so a build here
# reproduces a sync there.
FROM ghcr.io/astral-sh/uv:0.11.24 AS uv

FROM python:3.13-slim-bookworm

# HTTPS to Wikipedia during ingestion, to Hugging Face during the build, and to
# OpenAI on every answer.
RUN apt-get update \
    && apt-get install --no-install-recommends --yes ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=uv /uv /usr/local/bin/uv

WORKDIR /app

# Bytecode up front trades build time for start time, and copying rather than
# hardlinking keeps uv's cache from crossing the layer boundary.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PATH="/app/.venv/bin:$PATH"

# Dependencies before source, so editing a module does not re-resolve the lock
# file. README.md and LICENSE are here because pyproject.toml names them and the
# build backend reads them.
COPY pyproject.toml uv.lock README.md LICENSE ./
RUN uv sync --locked --no-dev --no-install-project

COPY src/ ./src/
RUN uv sync --locked --no-dev

# Both models land in /app/models, where the encoder and the reranker look for
# them. Pinned revisions mean this layer is stable until a model changes.
RUN python -m supernatural_expert.embedding \
    && python -m supernatural_expert.reranking

COPY docker/container.env docker/entrypoint.sh ./docker/
RUN chmod +x docker/entrypoint.sh

# dlt keeps its working files under the repository rather than in ~/.dlt, and the
# pipeline expects to be able to write here.
RUN mkdir -p .cache/dlt

EXPOSE 8501

ENTRYPOINT ["/app/docker/entrypoint.sh"]
