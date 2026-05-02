# Set up with GitHub Codespaces

A Codespace gives you a full, pre-configured workshop environment running in the cloud — accessible from your browser or from VS Code on your laptop. 

This repo's Dev Container has be made into a **prebuilt image**, so a fresh Codespace boots in roughly a minute instead of the several minutes a cold dev-container build, or manual requirements install would take.

## Recommended: launch the Codespace from the upstream repo

Click the badge below to start a Codespace directly from the workshop's upstream repository:

[![Open in GitHub Codespaces](https://github.com/codespaces/badge.svg)](https://codespaces.new/sarahlevins/ai-podcast-workshop)

When the "Create Codespace" page loads, choose:

- **Branch:** `main`
- **Region:** the closest one to you
- **Machine type:** **2-core • 8 GB RAM • 32 GB storage** (the workshop is sized to fit this; bigger machines cost more though, so keep that in mind)

Click **Create codespace**. The first launch should pull the prebuilt image and have you in a working VS Code session within a minute or two.

> **Why launch from the upstream repo and not a fork?** Codespaces **prebuilds are scoped to the repository they're configured on**. The upstream `sarahlevins/ai-podcast-workshop` repo has prebuilds configured for `main`, so a Codespace started there reuses the cached image. **Forks do not inherit prebuilds** — a Codespace launched on your fork will rebuild the dev container image from the Dockerfile on first start, which can take 5–10+ minutes. For a workshop, that wait is usually not worth it.

## "But I want to save my changes"

You don't need to fork to keep your work — a few options:

- **Commit to a branch on the upstream repo** if you have write access (workshop attendees usually don't).
- **Fork after the fact and push there.** Inside the Codespace, change the remote to point at your fork:
  ```bash
  git remote set-url origin https://github.com/<your-username>/ai-podcast-workshop.git
  git push -u origin <your-branch>
  ```
  You'll be prompted to authenticate with your GitHub account.
- **Just download the files** from the Codespace if you only want a copy of your edits at the end of the workshop.

## If you'd rather use a fork (slower first launch)

If you specifically want the Codespace to live on your own fork — e.g. you'll keep working on it after the workshop and want everything in one place — that works too, with the caveat that the **first** Codespace start will rebuild the dev container from scratch.

1. Fork [`sarahlevins/ai-podcast-workshop`](https://github.com/sarahlevins/ai-podcast-workshop) to your own account
2. On your fork, click **Code → Codespaces → Create codespace on main**
3. Pick the same machine type as above (**2-core • 8 GB RAM • 32 GB**)
4. Wait for the dev container to build. Subsequent starts of the same Codespace are fast — only the first build is slow.

## Verify the environment

Once the Codespace is open, you'll be in VS Code with the repo loaded. The dev container has Python, the workshop dependencies, and (in the prebuilt image) the Ollama models already in place. You don't need to run `pip install` — just open the [setup test notebook](../setup-test.ipynb) and pick the **AI Podcast Studio** kernel to confirm everything works.

---

When you're done here, return to [Environment Setup Step 2](../README.md#2-choose-and-configure-your-model-provider) to choose and configure your model provider.
