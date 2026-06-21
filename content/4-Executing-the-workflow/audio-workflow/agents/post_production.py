"""Post-Production agent — loads output/agents/post-production.md."""

import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[5]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from utils.agents import create_agent, AgentOptions  # noqa: E402

AGENTS_DIR = WORKSPACE / "output" / "agents"


def create_post_production(show_context: str):
    role_def = (AGENTS_DIR / "post-production.md").read_text()
    return create_agent(AgentOptions(
        name="PostProduction",
        instructions=show_context + "\n\n---\n\n" + role_def,
    ))
