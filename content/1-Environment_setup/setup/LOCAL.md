# Local setup

You have two options for running this workshop locally: a **Python virtual environment** (lightest, fastest to set up) or a **Dev Container** (uses the same prebuilt image as Codespaces — slower to start but matches the workshop environment exactly).

## Option A — Python virtual environment

You'll need **Python 3.10 or newer** installed. Check with:

```bash
python3 --version
```

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

Pick the commands for your operating system:

#### macOS / Linux

```bash
python -m venv .venv # or python3 -m venv .venv
source .venv/bin/activate
```


#### Windows (Command Prompt)

```cmd
python -m venv .venv
.\.venv\Scripts\activate.bat
```

You should now see `(.venv)` at the start of your shell prompt — that means the environment is active.

### 3. Install the dependencies

```bash
pip install --upgrade pip
pip install -r .devcontainer/requirements.txt
pip install -e .
```

This will install all external and internal dependencies

### 4. (Optional) Select the venv in VS Code

Open the Command Palette (`Cmd/Ctrl + Shift + P`) → **Python: Select Interpreter** → pick the one inside `.venv`. This makes notebooks and scripts run against the right environment.

To leave the environment later, run `deactivate`.

---

## Option B — Dev Container

If you have Docker Desktop and the **Dev Containers** VS Code extension installed, you can reopen the repo in the same container the Codespace uses:

1. Open the repo in VS Code
2. `Cmd/Ctrl + Shift + P` → **Dev Containers: Rebuild and Reopen in Container**
3. Wait for the image to build (this can take several minutes the first time)

Everything is preinstalled inside the container — no `pip install` step needed.

---

When you're done, return to [Environment Setup Step 2](../README.md#2-choose-and-configure-your-model-provider) to configure your model provider.
