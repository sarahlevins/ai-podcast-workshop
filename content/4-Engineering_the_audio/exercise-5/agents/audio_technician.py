"""Audio Technician agent — loads output/agents/audio-technician.md.

Merges Whisper timestamps + music plan + original transcript into a unified
timestamped transcript JSON.
"""

import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[4]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from utils.agents import create_agent, AgentOptions  # noqa: E402

AGENTS_DIR = WORKSPACE / "output" / "agents"


def create_audio_technician(show_context: str):
    role_def = (AGENTS_DIR / "audio-technician.md").read_text()
    return create_agent(AgentOptions(
        name="AudioTechnician",
        instructions=show_context + "\n\n---\n\n" + role_def,
    ))
