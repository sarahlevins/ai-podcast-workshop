FROM mcr.microsoft.com/devcontainers/python:3.12

# Install Ollama
RUN apt-get update && apt-get install -y zstd && rm -rf /var/lib/apt/lists/*
RUN curl -fsSL https://ollama.com/install.sh | sh

# Pull the model during build so it's baked into the image.
# Run as vscode so blobs land in /home/vscode/.ollama, where ollama serve
# will look at runtime in the devcontainer/Codespace.
USER vscode
RUN ollama serve & \
    SERVE_PID=$! && \
    sleep 5 && \
    ollama pull gemma4:e4b && \
    kill $SERVE_PID && \
    wait $SERVE_PID 2>/dev/null || true
USER root

# Install Node.js
RUN curl -fsSL https://deb.nodesource.com/setup_22.x | bash - && \
    apt-get install -y nodejs && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY AgentCampWorkshop/code/Installations/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt -U
