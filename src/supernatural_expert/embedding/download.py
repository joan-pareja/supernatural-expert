"""Fetch a pinned ONNX model into `models/`, ready to run.

Downloading is separate from encoding so the network is touched once, during
setup, and never from application code. Repeating it is safe and cheap: files
already present are left alone.

Any pinned repository holding an ONNX graph and a tokenizer arrives this way, so
the cross-encoder in `supernatural_expert.reranking` reuses it rather than
carrying a second copy of the same fetch.

`hf_hub_download` and `list_repo_files` are the only Hugging Face calls made
here, and neither reports usage, so nothing has to be opted out of.
"""

import shutil
from pathlib import Path

from huggingface_hub import (
    hf_hub_download,  # pyright: ignore[reportUnknownVariableType]
    list_repo_files,
)

from supernatural_expert.embedding.models import DEFAULT_MODEL, OnnxModel

# Repositories disagree on where the graph sits, so the first match wins.
ONNX_CANDIDATES = ("onnx/model.onnx", "onnx/encoder_model.onnx", "model.onnx")


class ModelDownloadError(RuntimeError):
    """Raised when a repository holds no ONNX graph we can use."""


def download_model(model: OnnxModel = DEFAULT_MODEL) -> Path:
    """Place `model.onnx` and `tokenizer.json` in the model's directory."""
    directory = model.directory
    directory.mkdir(parents=True, exist_ok=True)

    published = list_repo_files(repo_id=model.repository, revision=model.revision)
    graph = next((name for name in ONNX_CANDIDATES if name in published), None)
    if graph is None:
        raise ModelDownloadError(
            f"{model.repository} at {model.revision[:7]} publishes no ONNX graph. "
            f"Looked for {', '.join(ONNX_CANDIDATES)}."
        )

    wanted = [(graph, "model.onnx"), ("tokenizer.json", "tokenizer.json")]
    # Graphs above 2 GB keep their weights in a sidecar file that must travel
    # with them. Small models such as MiniLM never have one.
    if f"{graph}_data" in published:
        wanted.append((f"{graph}_data", "model.onnx_data"))

    for remote, local in wanted:
        destination = directory / local
        if destination.exists():
            print(f"  present  {destination}")
            continue
        cached = hf_hub_download(
            repo_id=model.repository, filename=remote, revision=model.revision
        )
        shutil.copy2(cached, destination)
        print(f"  saved    {destination}")

    return directory


def main() -> int:
    model = DEFAULT_MODEL
    print(f"{model.repository} at {model.revision[:7]}")
    directory = download_model(model)
    print(
        f"Ready. {model.dimensions} dimensions, {model.max_tokens} tokens, {directory}"
    )
    return 0
