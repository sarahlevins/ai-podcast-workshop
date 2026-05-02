# Understanding the Workflow (10 minutes)

Before writing any code, we need to understand what we're building.

## What makes a good podcast?

- **Host chemistry** — Hosts have distinct roles, not two people saying the same thing.
- **Structure** — Strong hook, clear segments, satisfying wrap-up.
- **Conversational tone** — Feels like eavesdropping on a smart conversation, not a lecture.
- **Pacing** — Mix of light moments and deep dives, varied segment lengths.
- **Complementary hosts** — One asks questions the audience would ask, the other has expertise. They complement each other, not duplicate.

## How podcasts are made (the workflow)

1. **Research & Topic Selection** — Find a compelling angle, gather facts, stats, and recent developments.
2. **Script / Outline Writing** — Structure the episode: hook, intro, segments, conclusion.
3. **Recording** — Hosts bring distinct perspectives, natural conversation, real reactions.
4. **Editing & Post-Production** — Tighten the script, ensure pacing, check host voice consistency.
5. **Publishing** — Export the final output.

## Defining host personalities

When defining an AI host, consider these dimensions:

| Dimension | Example: Curious Host | Example: Expert |
|-----------|---------------------|----------------------|
| **Role** | Asks questions, guides conversation | Provides answers, adds depth |
| **Knowledge level** | Curious beginner | Deep expertise |
| **Speaking style** | Short sentences, analogies | Structured explanations, examples |
| **Humor** | Playful, puns | Dry, deadpan |
| **Catchphrases** | "Wait, what?", "Break that down for me" | "Well actually...", "Here's the thing" |
| **Emotional range** | Excited, surprised, skeptical | Measured, occasionally passionate |
| **Conflict style** | Pushes for simpler explanations | Pushes back on oversimplification |

Good hosts **complement** each other. One asks, one answers. One gets excited, one stays grounded. This tension is what makes podcasts engaging — and it's exactly what we need to capture in our agent instructions.

## Exercise: Create your podcast agent artifacts

You need one filled-in instruction artifact per role in the pipeline:

- **Producer Agent** — Generates a compelling episode angle, title, and talking points.
- **Research Agent** — Finds recent facts, stats, and examples for each talking point.
- **Script Writer Agent** — Writes a multi-speaker podcast script with distinct host voices.
- **Editor Agent** — Tightens the script, checks pacing, ensures hosts sound distinct.
- **Publisher Agent** — Saves the final approved script to a file.

The templates live here:

- [templates/agent-instruction-templates/](templates/agent-instruction-templates) — one role template per agent. Each contains three placeholders: `{{PODCAST_CONCEPT}}`, `{{PODCAST_CONCEPT_DESCRIPTION}}`, and `{{HOST_DEFINITIONS}}`.
- [templates/host-definition-templates/](templates/host-definition-templates) — drop-in host archetypes (curious host, expert, skeptic, storyteller, practitioner, comic relief).

Pick one of the three paths below. All of them produce the same output: a `podcast-agent-artifacts/` folder inside `content/2-Understanding_the_workflow/` containing five filled-in role files.

---

### Option A — Run the Python agent builder (recommended)

The [`podcast-agent-builder-agent/`](podcast-agent-builder-agent) module runs an agentic workflow using the agent-framework CLI and the model you set up via the .env

1. From the repo root, run:
   ```
   python content/2-Understanding_the_workflow/podcast-agent-builder-agent/agent-artifact-builder.py
   ```
2. When prompted, describe your podcast concept in a sentence or two.
3. The agent will propose a host line-up — confirm or request changes. Make sure you only let it set 2 hosts (so the models can handle all that chatter!)
4. It will write the five agent artifacts to `content/2-Understanding_the_workflow/podcast-agent-artifacts/`.

---

### Option B — Use your own external agent

Use an agent of your choice. Copy the `agent-artifact-builder.txt` file into an LLM you have a subscription to that can handle creative tasks, and then copy the files it generates into `content/2-Understanding_the_workflow/podcast-agent-artifacts/`

---

### Option C — Fill the templates in by hand

If you'd rather see the seams, do the substitution yourself.

1. Create a `podcast-agent-artifacts/` folder inside `content/2-Understanding_the_workflow/`.
2. Copy each file from [templates/agent-instruction-templates/](templates/agent-instruction-templates) into it.
3. Pick 2 hosts from [templates/host-definition-templates/](templates/host-definition-templates) (or write your own using the dimensions in the table above). Aim for complementary roles — curious + expert, skeptic + storyteller, expert + comic relief.
4. In every copied artifact, replace:
   - `{{PODCAST_CONCEPT}}` with a short show name.
   - `{{PODCAST_CONCEPT_DESCRIPTION}}` with a 2–4 sentence pitch.
   - `{{HOST_DEFINITIONS}}` with the contents of your chosen host files, concatenated.

---

Once you have all five files in `podcast-agent-artifacts/`, you're ready for the next section.
