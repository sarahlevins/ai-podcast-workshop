# Environment Setup (15 minutes)

### 1. Choose an environment

| Option | Description | Requirements | Setup Steps |
|--------|-------------|--------------|--------------|
| **Codespace (RECOMMENDED)**| Pre-built environment with code and models pre-installed. Just open and go. | GitHub account. GitHub spend may apply. | [Github Codespace](./_resources/codespace.md) |
| **Local** | Fork and clone this repo, Open in VS Code in dev container or install requirements locally | Python 3.12+, ffmpeg, Azure subscription | [Local](./_resources/local.md) |

### 2. Choose a model provider

We'll be running agents via notebooks and scripts through the agent-framework, which supports several model providers. Pick the one that matches your setup:

| Provider | When to use it | Speed | `MODEL_PROVIDER` | What to configure in .env | Set up instuctions |
|----------|----------------|-------|------------------|---------------------------|-------------------|
| **Azure AI Foundry (RECOMMENDED)** | You have an Azure subscription and a deployed model. Best performance and the most production-like experience. | Fastest | `foundry` | `FOUNDRY_PROJECT_ENDPOINT`, `FOUNDRY_MODEL`, `FOUNDRY_API_KEY` | [Azure AI Foundry](./_resources/azure_ai_foundry.md) |
| **Ollama** | You have a model pulled locally, or you're using the prebuilt Codespace (models are baked in). Works fully offline but is the slowest option. | Slowest | `ollama` | `OLLAMA_HOST`, `OLLAMA_CHAT_MODEL_ID` | [Ollama](./_resources/ollama.md) |

### 3. Test your setup

Open the [Setup Test Notebook](./exercise-0/setup-test.ipynb) and run some commands that sets up some agents and sends some prompts to test everything is working correctly.

When running the notebook, be sure to select the .venv as your python kernel

1. Up the top right hand corner of the notebook file, select `Select Kernel`
    - If you are running this in a codespace or dev container, select `Jupyter Kernels` then select the one titled `Workshop`
    - If you are running this in your local environment, ensure you have a virtual environment with the requirements installed, and select that Python Environment

### Setup Complete - [Move on to Section 2](../2-Developing_the_concept/readme.md)