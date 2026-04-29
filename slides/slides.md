---
theme: seriph
background: https://images.unsplash.com/photo-1478737270239-2f02b77fc618?w=1920
title: The AI Podcast Studio
info: Build an AI-powered podcast production pipeline using Microsoft Agent Framework
class: text-center
drawings:
  persist: false
transition: slide-left
---

# The AI Podcast Studio

Build an AI-powered podcast pipeline with Microsoft Agent Framework

<div class="abs-br m-6 flex gap-2">
  <a href="https://github.com/microsoft/edgeai-for-beginners" target="_blank" class="text-xl slidev-icon-btn opacity-50 !border-none !hover:text-white">
    <carbon-logo-github />
  </a>
</div>

---
layout: center
---

# Agenda

| | Section | Time |
|---|---------|------|
| 1 | Introduction | 5 min |
| 2 | Environment Setup | 10 min |
| 3 | Understanding the Workflow | 10 min |
| 4 | Creating the Workflow | 20 min |
| 5 | Executing the Workflow | 15 min |

---
layout: section
---

# 1. Introduction
Why are we here?

---

# Why build a podcast with AI?

<v-clicks>

- Podcasts are a great tool for **learning and relaxing** — it would be handy to tailor-make them for yourself

- There are some cool **AI tools** out there we can explore by using them to make a podcast

- To build effective AI automations, you need to understand how to **translate real-world concepts** into AI orchestration

</v-clicks>

---

# What you'll leave with

<v-clicks>

**Agent Templates**
Tools for writing agent templates for different roles within an orchestration

**Workflow Translation**
Understanding of how to translate a real-world workflow into an AI orchestration workflow

**Agent Framework SDK**
Methods to orchestrate agents using the Microsoft Agent Framework SDK in Python

</v-clicks>

---

# What this workshop is based on

<br>

This workshop builds on Microsoft's **Edge AI for Beginners** curriculum, adapted for a focused, hands-on 1 hour experience.

<br>

```
github.com/microsoft/edgeai-for-beginners
```

---
layout: section
---

# 2. Environment Setup
Getting your tools ready (10 min)

---

# Choose your setup

<br>

| Option | Description | Requirements |
|--------|-------------|--------------|
| **Codespace** | Pre-built environment with code and models. Just open and go. | GitHub account |
| **Local + Foundry** | Clone repo, use a model in Azure AI Foundry. | Python 3.10+, Azure sub |
| **Local + Copilot** | Clone repo, use GitHub Copilot CLI as provider. | Python 3.10+, Copilot access |

<br>

<v-click>

**Codespace is recommended** — everything is pre-installed.

GitHub spend may apply.

</v-click>

---

# Setup steps

<v-clicks>

1. Open the Codespace (or fork & clone locally)

2. Run the setup script to create a virtual environment

```bash
source code/setup.sh
```

3. Configure your `.env` with your model provider

```bash
cp code/.env.examples code/.env
```

4. Select the **AI Podcast Studio** Jupyter kernel in VS Code

</v-clicks>

---
layout: section
---

# 3. Understanding the Workflow
Before writing code, understand what we're building (10 min)

---

# What makes a good podcast?

<v-clicks>

- **Host chemistry** — Distinct roles, not two people saying the same thing

- **Structure** — Strong hook, clear segments, satisfying wrap-up

- **Conversational tone** — Feels like eavesdropping on a smart conversation, not a lecture

- **Pacing** — Mix of light moments and deep dives

- **Complementary hosts** — One asks, one answers. One gets excited, one stays grounded.

</v-clicks>

---

# How podcasts are made

The real-world workflow we're translating into AI:

<v-clicks>

1. **Research & Topic Selection** — Find a compelling angle, gather facts and stats

2. **Script / Outline Writing** — Structure the episode: hook, intro, segments, conclusion

3. **Recording** — Hosts bring distinct perspectives, natural conversation

4. **Editing & Post-Production** — Tighten the script, check pacing and consistency

5. **Publishing** — Export the final output

</v-clicks>

---

# Defining host personalities

When defining an AI host, consider these dimensions:

| Dimension | Lucy (Host) | Ken (Expert) |
|-----------|-------------|--------------|
| **Role** | Asks questions, guides conversation | Provides answers, adds depth |
| **Knowledge level** | Curious beginner | Deep expertise |
| **Speaking style** | Short sentences, analogies | Structured explanations |
| **Humor** | Playful, puns | Dry, deadpan |
| **Catchphrases** | "Wait, what?" | "Well actually..." |
| **Emotional range** | Excited, surprised | Measured, passionate |
| **Conflict style** | Pushes for simpler explanations | Pushes back on oversimplification |

---

# Translating hosts into agent instructions

```python {all|3-4|5-6|7-8|all}
create_agent(AgentOptions(
    name="ScriptAgent",
    instructions="""You write scripts for "Future Bytes",
    a 10-minute tech podcast.

    HOSTS:
    - Lucy (Host): Curious, enthusiastic, asks the questions
      listeners would ask. Uses analogies. Punchy sentences.
    - Ken (Expert): Deep technical knowledge, explains simply.
      Uses real-world examples. Dry humor.

    STYLE RULES:
    - No speaker talks for more than 3 lines in a row
    - Include reactions: "Wait, really?", "That's wild"
    - At least one analogy per segment
    """,
))
```

---
layout: two-cols
---

# Exercise: Define your agents

Use the templates to define your podcast pipeline agents:

<v-clicks>

- **Producer Agent**
  - Episode angle, title, talking points

- **Research Agent**
  - Facts, stats, examples per talking point

- **Script Writer Agent**
  - Multi-speaker script with distinct voices

- **Editor Agent**
  - Tighten, check pacing, verify host consistency

- **Publisher Agent**
  - Save approved script to file

</v-clicks>

::right::

<div class="pl-4">

```python
# Example: Producer Agent
create_agent(AgentOptions(
    name="ProducerAgent",
    instructions="""You are a podcast
    producer for "Future Bytes".

    Given a broad subject, generate:
    - A catchy episode title
    - 3-4 key talking points
    - A hook question to open with
    - Target audience: tech-curious
      beginners
    """,
))
```

```python
# Example: Research Agent
create_agent(AgentOptions(
    name="ResearchAgent",
    instructions="""You are a research
    assistant for a tech podcast.

    Find recent facts, statistics,
    and expert quotes. Focus on
    surprising findings that make
    good conversation starters.""",
    tools=[web_search],
))
```

</div>

---
layout: section
---

# 4. Creating the Workflow
Hands-on with the Agent Framework SDK (20 min)

---

# Explore: Jupyter Notebooks

Get familiar with the SDK basics:

<v-clicks>

- **Create an agent** with `create_agent(AgentOptions(...))`

- **Run a prompt** and view the response

- **Stream output** to see tokens as they arrive

- **Add tools** like web search to give agents capabilities

- **Observe reasoning** to understand how the model thinks

</v-clicks>

<br>

```
code/01.BasicAgent/00.BasicAgent-agent.ipynb
code/01.BasicAgent/01.BasicAgent-tools.ipynb
code/01.BasicAgent/03.BasicAgent-websearch.ipynb
```

---

# Explore: Dev UI

The Agent Framework Dev UI lets you test agents interactively.

```bash
python code/02.Workflow-MultiAgent/01.AgentDevUI/agent.py
```

<br>

<v-clicks>

- Chat with your agent in a web interface
- See tool calls and reasoning in real time
- Test different prompts and instructions

</v-clicks>

---

# The workflow architecture

```
TopicAgent -> ResearchAgent -> ScriptAgent -> ReviewExecutor -> EditAgent -> SaveExecutor
                                                   ^                |
                                                   |________________|
                                                  (rejection loop)
```

<br>

<v-clicks>

- **Agents** — AI-powered executors that use LLMs to process messages
- **Executors** — Custom logic components (like the review step)
- **Edges** — Connections that route messages between executors
- **Human-in-the-loop** — The ReviewExecutor pauses for your approval

</v-clicks>

---

# Building the workflow in code

```python {all|1-3|5-6|8-11|all}
# Wrap agents as executors
search_executor = AgentExecutor(agent=search_agent, id="search_executor")
script_executor = AgentExecutor(agent=script_agent, id="script_executor")

# Custom executors for review and save
review_executor = ReviewExecutor(id="review_executor")
save_executor = SaveScriptExecutor(id="save_executor")

# Wire them together
workflow = (
    WorkflowBuilder(start_executor=search_executor)
    .add_edge(search_executor, script_executor)
    .add_edge(script_executor, review_executor)
    .add_edge(review_executor, script_executor)   # rejection loop
    .add_edge(review_executor, save_executor)      # approval path
    .build()
)
```

---
layout: section
---

# 5. Executing the Workflow
Run it end-to-end (15 min)

---

# Run the full pipeline

<v-clicks>

1. **Plug in your agent artefacts** — Update the agent instructions with your host personalities and workflow definitions

2. **Launch the workflow** — Run through the Dev UI or from the command line

3. **Review the script** — Approve it, or reject with feedback to regenerate

4. **Generate audio** — Transform the approved script into speech with VibeVoice

5. **Listen to the results** — Your AI-produced podcast episode

</v-clicks>

---

# Running the workflow

```bash
# Launch the workflow Dev UI
python code/02.Workflow-MultiAgent/02.WorkflowDevUI/main.py
```

<br>

```bash
# Generate audio from the approved script
cd code/03.GenerationAudio
./run_vibe_voice.sh
```

---
layout: center
class: text-center
---

# Go build your podcast!

Plug in your agents, run the workflow, and listen to the results.

<br>

Ask for help if you get stuck.

---
layout: center
class: text-center
---

# Thank you

<br>

Built with Microsoft Agent Framework + Ollama + VibeVoice

[Edge AI for Beginners](https://github.com/microsoft/edgeai-for-beginners)
