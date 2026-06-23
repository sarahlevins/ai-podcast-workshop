"""Music Director agent — loads output/agents/music-director.md.

This agent is defined but not yet wired into the Episode Production Workflow.
See the TODO in workflow.py for the planned integration point.
"""

import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[4]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from utils.agents import create_agent, AgentOptions  # noqa: E402

AGENTS_DIR = WORKSPACE / "output" / "agents"


def create_music_director(show_context: str):
    role_def = (AGENTS_DIR / "music-director.md").read_text()
    return create_agent(AgentOptions(
        name="MusicDirector",
        instructions=show_context + "\n\n---\n\n" + role_def,
    ))
