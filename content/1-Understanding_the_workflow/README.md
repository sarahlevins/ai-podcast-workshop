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

## Exercise: Define your agent artefacts

You need one filled-in instruction artefact per role in the pipeline:

- **Producer Agent** — Generates a compelling episode angle, title, and talking points.
- **Research Agent** — Finds recent facts, stats, and examples for each talking point.
- **Script Writer Agent** — Writes a multi-speaker podcast script with distinct host voices.
- **Editor Agent** — Tightens the script, checks pacing, ensures hosts sound distinct.
- **Publisher Agent** — Saves the final approved script to a file.

The scaffolding for all of these lives in this folder:

- [agent-instruction-templates/](agent-instruction-templates) — one role template per agent. Each contains three placeholders: `{{PODCAST_CONCEPT}}`, `{{PODCAST_CONCEPT_DESCRIPTION}}`, and `{{HOST_DEFINITIONS}}`.
- [host-definition-templates/](host-definition-templates) — drop-in host archetypes (curious host, expert, skeptic, storyteller, practitioner, comic relief).
- [agent-artifact-builder.txt](agent-artifact-builder.txt) — instructions for an agent that does the assembly for you.

Pick one of the two paths below.

### Option A — Use the agent-artifact-builder agent (recommended)

Let an agent fill the templates in for you.

1. Spin up an agent (in Claude Code, GitHub Copilot, or whatever you're using) and load [agent-artifact-builder.txt](agent-artifact-builder.txt) as its instructions.
2. Give it your podcast concept in a sentence or two. Optionally pass in no more than 2 custom host definitions; if you don't, it will pick from the host templates.
3. Confirm (or change) its proposed host line-up when it asks.
4. It will write the five filled-in artefacts to `content/1-Understanding_the_workflow/agent-artifacts/`, one per role.

### Option B — Fill the templates in by hand

If you'd rather see the seams, do the substitution yourself.

1. Create an `agent-artifacts/` folder inside `content/1-Understanding_the_workflow/`.
2. Copy each file from [agent-instruction-templates/](agent-instruction-templates) into it.
3. Pick 2 hosts from [host-definition-templates/](host-definition-templates) (or write your own using the dimensions in the table above). Aim for complementary roles — curious + expert, skeptic + storyteller, expert + comic relief.
4. In every copied artefact, replace:
   - `{{PODCAST_CONCEPT}}` with a short show name.
   - `{{PODCAST_CONCEPT_DESCRIPTION}}` with a 2-4 sentence pitch.
   - `{{HOST_DEFINITIONS}}` with the contents of your chosen host files, concatenated.

Either way, the output is the same: five role-specific instruction files, ready to drop into `create_agent(...)` calls in the next section.
