# Building the Workflow (20 minutes)

## Explore Agent Framework Dev UI

The Dev UI lets you test agents interactively in a web interface.

```bash
python code/02.Workflow-MultiAgent/01.AgentDevUI/agent.py
```

- Chat with your agent in a browser
- See tool calls and reasoning in real time
- Test different prompts and instructions

## The Workflow Architecture

```
TopicAgent -> ResearchAgent -> ScriptAgent -> ReviewExecutor -> EditAgent -> SaveExecutor
                                                   ^                |
                                                   |________________|
                                                  (rejection loop)
```

### Key concepts

- **Agents** — AI-powered executors that use LLMs to process messages.
- **Executors** — Custom logic components (like the review step or saving to file).
- **Edges** — Connections that route messages between executors.
- **Human-in-the-loop** — The ReviewExecutor pauses the workflow for your approval.

### Building the workflow in code

```python
from agent_framework import WorkflowBuilder, AgentExecutor

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

### Running the workflow Dev UI

```bash
python code/02.Workflow-MultiAgent/02.WorkflowDevUI/main.py
```

This launches the workflow in a web interface where you can:
- Submit a topic to kick off the pipeline
- Watch each executor process its step
- Approve or reject the generated script
- See the final output saved to a file
