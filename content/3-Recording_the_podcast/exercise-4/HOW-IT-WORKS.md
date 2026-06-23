# How the Recording Workflow Works

This workflow simulates a live podcast recording session using AI agents. Think of it like a real recording studio, but everyone in the room — the researcher, the producer, and the hosts — is an AI.

---

## The Cast

| Role | What they do |
|---|---|
| **Researcher** | Looks up background info on the episode topic |
| **Recording Producer** | Plans the show structure and keeps things on track |
| **Host A & Host B** | Have the actual conversation |
| **Transcript Assembler** | Tidies up the raw conversation into a clean transcript |

---

## What Happens, Step by Step

### Step 1 — Research
When you kick off the workflow with an episode topic (e.g. *"the impact of AI on creative writing"*), the **Researcher** goes first. It produces a thorough set of notes covering key facts, angles, and interesting talking points the hosts can draw on.

### Step 2 — Hosts Do Their Homework
Before anyone goes on air, each host reads the research notes and makes their own personal "cheat sheet" — pulling out only the points and angles that fit their voice and style. Host A goes first, then Host B. This keeps the conversation feeling natural rather than both hosts robotically reciting the same facts.

### Step 3 — Producer Opens the Session
The **Recording Producer** reads all the research, then writes a session plan: a list of segments (like *Cold Open*, *Main Discussion*, *Outro*), how long each should run, and an opening question to kick things off.

### Step 4 — The Recording Loop (the main event)
This is where the actual conversation happens. Picture it as a back-and-forth in a chat room, managed by an invisible stage manager:

1. **Host A speaks** — one utterance at a time (a few sentences)
2. **Host B reacts** — they either respond naturally, or silently pass if they have nothing to add
3. The stage manager decides who speaks next, then repeats

Every **5 utterances**, the Producer checks in and makes a call:
- **CONTINUE** — great, keep going in this segment
- **TRANSITION** — time to move to the next segment
- **REDIRECT** — course-correct (hosts went off track)
- **DONE** — wrap it up

The Producer also watches the **clock**. It estimates time by counting words and dividing by 130 (a typical speaking rate in words per minute), so it knows when to start the outro.

### Step 5 — Transcript Assembly
Once the Producer calls it done, the raw conversation log gets handed to the **Transcript Assembler**, which reformats everything into a clean, structured JSON file — the final podcast transcript.

---

## The Outputs

| File | What it is |
|---|---|
| `output/episodes/<date>-<slug>/workflow-output/transcript.json` | The finished transcript |
| `output/workflow-runs/script/<run-id>/recording/utterances.json` | Every utterance logged as it happened |
| `output/workflow-runs/script/<run-id>/recording/producer_brief.md` | The producer's session plan |
| `output/workflow-runs/script/<run-id>/recording/research_notes.md` | The researcher's notes |

---

## How to Run It

```bash
python content/3-Recording_the_podcast/exercise-4/workflow.py
```

Then open the Dev UI at `http://localhost:8091` and type an episode brief (e.g. *"why cats sleep so much"*) to start the recording.

You can also pass the brief directly on the command line:

```bash
python content/3-Recording_the_podcast/exercise-4/workflow.py --brief "why cats sleep so much"
```

---

## A Quick Visual

```
[You type a topic]
       ↓
  Researcher — gathers background notes
       ↓
  Host A — reads notes, makes personal cheat sheet
       ↓
  Host B — reads notes, makes personal cheat sheet
       ↓
  Producer — writes the segment plan + opening question
       ↓
  ┌─────────────────────────────────┐
  │  Recording Loop                 │
  │  Host A speaks → Host B reacts  │
  │  ↕  (repeat)                    │
  │  Producer checks in every 5 turns│
  └─────────────────────────────────┘
       ↓
  Transcript Assembler — converts the raw log to JSON
       ↓
  [transcript.json saved to disk]
```
