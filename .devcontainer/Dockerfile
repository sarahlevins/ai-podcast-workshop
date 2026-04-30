FROM mcr.microsoft.com/devcontainers/python:3.12

# Create a venv at /opt/venv, owned by vscode, and put it first on PATH.
# Living outside /workspaces means the workspace bind-mount can't shadow it.
RUN python -m venv /opt/venv && chown -R vscode:vscode /opt/venv
ENV VIRTUAL_ENV=/opt/venv
ENV PATH=/opt/venv/bin:$PATH

# Install pinned Python dependencies into the venv at build time.
COPY .devcontainer/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /tmp/requirements.txt

# Register the venv as a named Jupyter kernel so notebooks pick it up by default.
RUN python -m ipykernel install --name workshop --display-name "Workshop (Python 3.12)"

# Auto-activate the venv in interactive shells so the prompt shows (venv)
# and `python`/`pip` resolve to /opt/venv even in login shells.
RUN echo 'source /opt/venv/bin/activate' >> /home/vscode/.bashrc \
    && chown vscode:vscode /home/vscode/.bashrc

# ---------------------------------------------------------------------------
# Pre-cache VibeVoice-1.5B model weights so participants don't wait for a 3 GB
# download at runtime.  The HF cache lives under the vscode user's home so
# from_pretrained() finds it automatically.
# ---------------------------------------------------------------------------
ENV HF_HOME=/home/vscode/.cache/huggingface
RUN pip install --no-cache-dir huggingface_hub \
    && huggingface-cli download vibevoice/VibeVoice-1.5B \
    && chown -R vscode:vscode /home/vscode/.cache

# ---------------------------------------------------------------------------
# Optional: Ollama (local LLM). Uncomment the blocks below to bake Ollama and
# a pre-pulled model into the image. When re-enabling, also restore the
# `postStartCommand` and the `11434` port forward in devcontainer.json.
# ---------------------------------------------------------------------------

# Install Ollama (also requires zstd for model-blob decompression).
RUN apt-get update \
    && apt-get install -y zstd \
    && rm -rf /var/lib/apt/lists/* \
    && curl -fsSL https://ollama.com/install.sh | sh

# Copy pre-downloaded Ollama models from the build context instead of pulling.
# Before building, run: cp -r ~/.ollama/models .devcontainer/ollama-models
# COPY .devcontainer/ollama-models /home/vscode/.ollama/models
# RUN chown -R vscode:vscode /home/vscode/.ollama

# Pre-pull a model into the vscode user's home so `ollama serve` finds it at runtime.
USER vscode
RUN ollama serve & \
    SERVE_PID=$! && \
    sleep 5 && \
    ollama pull mistral && \
    kill $SERVE_PID && \
    wait $SERVE_PID 2>/dev/null || true
USER root
