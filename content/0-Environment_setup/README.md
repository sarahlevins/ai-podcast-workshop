# Environment Setup (10 minutes)

Choose the setup that works best for you:

| Option | Description | Requirements |
|--------|-------------|--------------|
| **Codespace (recommended)** | Pre-built environment with code and models pre-installed. Just open and go. | GitHub account. GitHub spend may apply. |
| **Local + Azure AI Foundry** | Fork and clone this repo, run locally using an existing model deployed in Azure AI Foundry. | Python 3.10+, Azure subscription |
| **Local + GitHub Copilot** | Fork and clone this repo, run locally using GitHub Copilot CLI as the model provider. | Python 3.10+, GitHub Copilot access |

## Setup Steps

### 1. Open the Codespace (or fork & clone locally)

If running locally, fork and clone the repo, then continue with step 2.

### 2. Run the setup script

This creates a virtual environment and installs all dependencies:

```bash
source code/setup.sh
```

The script will:
- Create a `.venv` virtual environment if one doesn't exist
- Install all required packages
- Register a Jupyter kernel called **AI Podcast Studio**

**Note:** The script must be run with `source` (not `./` or `bash`) so the virtual environment activation persists in your shell. It supports both bash and zsh.

### 3. Configure your model provider

Copy the example env file and fill in your values:

```bash
cp code/.env.examples code/.env
```

Edit `code/.env` to set your `MODEL_PROVIDER`:

| Provider | `MODEL_PROVIDER` | What to configure |
|----------|-----------------|-------------------|
| **Ollama** (default) | `ollama` | `OLLAMA_HOST`, `OLLAMA_CHAT_MODEL_ID` |
| **GitHub Copilot** | `github-copilot` | `GITHUB_COPILOT_MODEL` |
| **Microsoft Foundry** | `foundry` | `FOUNDRY_PROJECT_ENDPOINT`, `FOUNDRY_MODEL`, `FOUNDRY_API_KEY` |

### 4. Select the Jupyter kernel in VS Code

When opening a notebook, select the **AI Podcast Studio** kernel from the kernel picker (under Jupyter Kernels, not Python Environments).
