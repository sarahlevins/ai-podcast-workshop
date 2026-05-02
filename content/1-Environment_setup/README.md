# Environment Setup (15 minutes)

### 1. Choose a setup and follow its instructions

| Option | Description | Requirements | Instructions |
|--------|-------------|--------------|--------------|
| **Codespace (recommended)** | Pre-built environment with code and models pre-installed. Just open and go. | GitHub account. GitHub spend may apply. | [Github Codespace](./setup/CODESPACE.md) |
| **Local** | Fork and clone this repo, run locally using an existing model deployed in Azure AI Foundry, or locally with GitHub Copilot. | Python 3.10+, Azure subscription | [Local](./setup/LOCAL.md) |

### 2. Choose and configure your model provider

We'll be running agents via notebooks and scripts through the agent-framework, which supports several model providers. Pick the one that matches your setup:

| Provider | When to use it | Speed | `MODEL_PROVIDER` | What to configure in .env |
|----------|----------------|-------|------------------|-------------------|
| **Azure AI Foundry** (recommended) | You have an Azure subscription and a deployed model. Best performance and the most production-like experience. | Fastest | `foundry` | `FOUNDRY_PROJECT_ENDPOINT`, `FOUNDRY_MODEL`, `FOUNDRY_API_KEY` |
| **Ollama** | You have a model pulled locally, or you're using the prebuilt Codespace (models are baked in). Works fully offline but is the slowest option. | Slowest | `ollama` | `OLLAMA_HOST`, `OLLAMA_CHAT_MODEL_ID` |

#### Azure AI Foundry Set Up
If you don't have a Foundry resource, and/or you don't have a model deployed, use the following instructions to get set up [***NOTE: Costs may apply***]:

[Azure AI Foundry Set Up Instructions](./setup/AZURE_AI_FOUNDRY.md)

#### Ollama Set Up
Ollama CLI allows you to download and locally run models. This is great if you don't want your data in the cloud and you don't want any surprise usage bills.

The prebuilt GitHub codespace image for this workshop has `llama3.2:3b` built into it, so if you want to use it - use the Codespace.

If you have ollama installed and models downloaded locally already - great! Use that.

If you want to get set up with Ollama localy for the first time you can run the follwing to install the cli:

```bash
# Install Ollama (also requires zstd for model-blob decompression).
apt-get update \
&& apt-get install -y zstd \
&& rm -rf /var/lib/apt/lists/* \
&& curl -fsSL https://ollama.com/install.sh | sh
```

Then you can download and run models:
```bash
# start the ollama process
ollama serve
# download and run a prompt on the model. The model will be cached locally
# and stay loaded into RAM for 10m
ollama run llama3.2:3b "Hi how are you?" 
```

***NOTE: this is not recommended for this workshop, because the download and installation will take some time ***

---

Once you have chosen and set up your model get the required values and populate the `.env` file in root.

1. Copy the example .env
```bash
cp .env.example /.env
```

2. Edit `.env` to set your values as described in the table above

### 4. Test your setup

Open the [Setup Test Notebook](./setup-test.ipynb) and select the appropriate **AI Podcast Studio** kernel from the kernel picker (under Jupyter Kernels, not Python Environments).

Your requests to agents should show their responses