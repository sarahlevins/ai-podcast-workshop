"""Audio Engineer agent — loads output/agents/audio-engineer.md.

The agent's behaviour depends on the chosen backend:
  mai2       → calls mai-2.py programmatically to generate audio segments
  vibevoice  → outputs step-by-step instructions for the user to run in a notebook
"""

import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[5]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from utils.agents import create_agent, AgentOptions  # noqa: E402

AGENTS_DIR = WORKSPACE / "output" / "agents"


def create_audio_engineer(show_context: str):
    role_def = (AGENTS_DIR / "audio-engineer.md").read_text()
    return create_agent(AgentOptions(
        name="AudioEngineer",
        instructions=show_context + "\n\n---\n\n" + role_def,
    ))
