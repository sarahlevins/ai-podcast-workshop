# Environment Setup (10 minutes)

### 1. Choose a setup and follow its instructions

| Option | Description | Requirements | Instructions |
|--------|-------------|--------------|--------------|
| **Codespace (recommended)** | Pre-built environment with code and models pre-installed. Just open and go. | GitHub account. GitHub spend may apply. | [Github Codespace](./setup/CODESPACE.md) |
| **Local** | Fork and clone this repo, run locally using an existing model deployed in Azure AI Foundry, or locally with GitHub Copilot. | Python 3.10+, Azure subscription | [Local](./setup/LOCAL.md) |

### 2. Choose and configure your model provider

We'll be running agents via notebooks and scripts through the agent-framework, which supports several model providers. Pick the one that matches your setup:

| Provider | When to use it | Speed | `MODEL_PROVIDER` | What to configure |
|----------|----------------|-------|------------------|-------------------|
| **Azure AI Foundry** (recommended) | You have an Azure subscription and a deployed model. Best performance and the most production-like experience. | Fastest | `foundry` | `FOUNDRY_PROJECT_ENDPOINT`, `FOUNDRY_MODEL`, `FOUNDRY_API_KEY` |
| **GitHub Copilot** | You have the GitHub Copilot CLI installed locally and an active Copilot subscription. No extra cloud setup. | Fast | `github-copilot` | `GITHUB_COPILOT_MODEL` |
| **Ollama** | You have a model pulled locally, or you're using the prebuilt Codespace (models are baked in). Works fully offline but is the slowest option. | Slowest | `ollama` | `OLLAMA_HOST`, `OLLAMA_CHAT_MODEL_ID` |

We recommend you use Azure AI Foundry as it will be the fastest/most performant. It may be subject to cost depending on your Azure Subscription. If you would like to use it as your provider, follow [these instructions](./setup/AZURE_AI_FOUNDRY.md) to set it up and get an API key.

Copy the example env file and fill in your values:

```bash
cp code/.env.examples code/.env
```

Then edit `code/.env` to set your `MODEL_PROVIDER` and the matching configuration values from the table above.

### 4. Test your setup

Open the [Setup Test Notebook](./setup-test.ipynb) and select the appropriate **AI Podcast Studio** kernel from the kernel picker (under Jupyter Kernels, not Python Environments).

Your requests to agents should show their responses