# Agent Definitions

## Source of truth

Agent prompt files live in:

```
content/2-Developing_the_concept/exercise-1/resources/agents/
```

This directory is committed to git. **Always edit agent prompts here.**

## How output agents are generated

When the Show Setup Workflow runs, it reads the source templates and writes show-specific versions to:

```
output/agents/
```

Each output file gets a show-specific header prepended (e.g. `_This agent serves the **Smoke Signals** podcast._`) and, for host agents, template placeholders like `{{HOST_NAME}}` are filled in from `output/show_context.md`.

The `output/` directory is not committed — it is regenerated per show.

## Keeping them in sync

Because the workflows read from `output/agents/` at runtime, you need both directories to reflect your changes:

1. **Edit the source file** in `content/2-Developing_the_concept/exercise-1/resources/agents/`.
2. **Apply the same change** to the corresponding file in `output/agents/` so the running workflow picks it up immediately without re-running Show Setup.

The output file has the show-specific header on its first two lines — preserve that when editing. Everything below line 2 should match the source file.

### Which output files map to which source files

| Source (`content/.../resources/agents/`) | Output (`output/agents/`) |
|---|---|
| `recording-producer.md` | `recording-producer.md` |
| `recording-host.md` | `host-<name>-recording.md` (one per host) |
| `host.md` | `host-<name>.md` (one per host) |
| `<agent>.md` | `<agent>.md` (direct copy + header) |

Host files in `output/agents/` are expanded from the template — do not sync back to source unless you are changing the template structure itself.

## What NOT to sync back

- `output/agents/host-*.md` — these are show-specific expansions of the `host.md` / `recording-host.md` templates.
- The show-specific header line (`_This agent serves the …_`) — this is added by the workflow, not part of the source.
- `output/agents/audio-engineer.md`, `output/agents/post-production.md` — legacy files, no longer used.
