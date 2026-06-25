# Local setup

| Option | Best for | Requirements |
|---|---|---|
| **A — Dev Container** | Closest match to the Codespace environment; no manual dependency installs | Docker Desktop, VS Code with Dev Containers extension |
| **B — Python virtual environment** | Lighter setup without Docker | Python 3.12+, ffmpeg |

---

## Option A — Dev Container

If you have Docker Desktop and the **Dev Containers** VS Code extension installed, you can reopen the repo in the same container the Codespace uses:

1. Open the repo folder in VS Code
2. `Cmd/Ctrl + Shift + P` → **Dev Containers: Rebuild and Reopen in Container**
3. Wait for the image to build (this can take several minutes the first time)

Everything — Python 3.12, ffmpeg, faster-whisper, and all pip dependencies — is preinstalled inside the container. No manual install steps needed.

---

## Option B — Python virtual environment

### Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.12+ | Check with `python --version` or `python3 --version` |
| ffmpeg | any recent | Needed for audio exercises (4 and 5) |

#### Install Python 3.12+

- **Mac**: Download from [python.org](https://www.python.org/downloads/) or `brew install python@3.12`
- **Windows**: Download from [python.org](https://www.python.org/downloads/) — check **"Add Python to PATH"** during install, or use `winget install Python.Python.3.12`

#### Install ffmpeg

- **Mac (Homebrew):**
  ```bash
  brew install ffmpeg
  ```
- **Windows (winget):**
  ```cmd
  winget install ffmpeg
  ```
- **Windows (Chocolatey):**
  ```cmd
  choco install ffmpeg
  ```
- **Windows (manual):** Download from [ffmpeg.org/download.html](https://ffmpeg.org/download.html), extract it, and add the `bin` folder to your system PATH.

Verify it's on PATH: `ffmpeg -version`

---

### 1. Fork and clone the repo

You'll work from your own fork so you can save changes to your GitHub account.

**a. Fork the repo on GitHub**

1. Open the workshop repo in your browser: <https://github.com/sarahlevins/ai-podcast-workshop>
2. Click the **Fork** button in the top-right corner
3. On the "Create a new fork" page, leave the defaults and click **Create fork**
4. You'll be redirected to your fork at `https://github.com/<your-username>/ai-podcast-workshop`

> Already have the GitHub CLI installed? You can do steps a–b in one shot:
> `gh repo fork sarahlevins/ai-podcast-workshop --clone`

**b. Clone your fork locally**

On your fork's GitHub page, click the green **Code** button and copy the HTTPS URL. Then in your terminal:

```bash
git clone https://github.com/<your-username>/ai-podcast-workshop.git
cd ai-podcast-workshop
```

(Replace `<your-username>` with your actual GitHub username.)

### 2. Create and activate a virtual environment

#### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
```

#### Windows (Command Prompt)

```cmd
python -m venv .venv
.\.venv\Scripts\activate.bat
```

#### Windows (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

> If PowerShell blocks the script with an execution policy error, run:
> `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`
> then try activating again.

You should see `(.venv)` at the start of your shell prompt — that means the environment is active.

### 3. Install the dependencies

```bash
pip install --upgrade pip
pip install -r .devcontainer/requirements.txt
pip install -e .
```

- `requirements.txt` installs the agent framework, Jupyter kernel, Azure Speech SDK, and faster-whisper
- `pip install -e .` installs the local `utils` package so notebooks can `import utils`

### 4. Select the venv in VS Code

Open the Command Palette (`Cmd/Ctrl + Shift + P`) → **Python: Select Interpreter** → pick the interpreter inside `.venv`. This makes notebooks and scripts use the right environment.

To leave the virtual environment later, run `deactivate`.

---

When you're done, return to [Environment Setup Step 2](content/1-Environment_setup/readme.md#2-choose-and-configure-your-model-provider) to configure your model provider.
