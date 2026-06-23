FROM mcr.microsoft.com/devcontainers/python:3.12

# Create a venv at /opt/venv, owned by vscode, and put it first on PATH.
# Living outside /workspaces means the workspace bind-mount can't shadow it.
RUN python -m venv /opt/venv && chown -R vscode:vscode /opt/venv
ENV VIRTUAL_ENV=/opt/venv
ENV PATH=/opt/venv/bin:$PATH

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg && rm -rf /var/lib/apt/lists/*

# faster-whisper uses CTranslate2 (not torch) so it works on Python 3.12
# with no openai SDK version conflict. whisper-cli==0.0.5 was an OpenAI API
# wrapper (needs old openai<0.28) and installs a binary called 'whisper' not
# 'whisper-cli', so it was both the wrong tool and had the wrong binary name.
RUN pip install --no-cache-dir faster-whisper

# Install pinned Python dependencies into the venv at build time.
COPY .devcontainer/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r /tmp/requirements.txt

# Register the venv as a named Jupyter kernel so notebooks pick it up by default.
RUN python -m ipykernel install --sys-prefix --name workshop --display-name "Workshop (Python 3.12)"

# Auto-activate the venv in interactive shells so the prompt shows (venv)
# and `python`/`pip` resolve to /opt/venv even in login shells.
RUN echo 'source /opt/venv/bin/activate' >> /home/vscode/.bashrc \
    && chown vscode:vscode /home/vscode/.bashrc

