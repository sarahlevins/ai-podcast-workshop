"""Researcher agent — loads output/agents/researcher.md as its system prompt."""

import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[5]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from utils.agents import create_agent, AgentOptions  # noqa: E402

AGENTS_DIR = WORKSPACE / "output" / "agents"


def create_researcher(show_context: str):
    role_def = (AGENTS_DIR / "researcher.md").read_text()
    return create_agent(AgentOptions(
        name="Researcher",
        instructions=show_context + "\n\n---\n\n" + role_def,
    ))
