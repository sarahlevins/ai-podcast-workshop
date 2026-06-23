"""Show Notes Writer agent — loads output/agents/show-notes-writer.md."""

import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[4]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from utils.agents import create_agent, AgentOptions  # noqa: E402

AGENTS_DIR = WORKSPACE / "output" / "agents"


def create_show_notes_writer(show_context: str):
    role_def = (AGENTS_DIR / "show-notes-writer.md").read_text()
    return create_agent(AgentOptions(
        name="ShowNotesWriter",
        instructions=show_context + "\n\n---\n\n" + role_def,
    ))
