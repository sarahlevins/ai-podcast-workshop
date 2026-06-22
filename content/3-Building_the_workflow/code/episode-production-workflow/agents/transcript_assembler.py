"""Transcript Assembler agent — loads output/agents/transcript-assembler.md."""

import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[5]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from utils.agents import create_agent, AgentOptions  # noqa: E402

AGENTS_DIR = WORKSPACE / "output" / "agents"


def create_transcript_assembler(show_context: str):
    role_def = (AGENTS_DIR / "transcript-assembler.md").read_text()
    return create_agent(AgentOptions(
        name="TranscriptAssembler",
        instructions=show_context + "\n\n---\n\n" + role_def,
    ))
