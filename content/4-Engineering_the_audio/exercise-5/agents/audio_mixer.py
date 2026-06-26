"""Audio Mixer agent — loads output/agents/audio-mixer.md.

Produces ffmpeg commands to cut, overlay, and combine audio into the final episode.
"""

import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[4]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from utils.agents import create_agent, AgentOptions  # noqa: E402

AGENTS_DIR = WORKSPACE / "4-Engineering_the_audio" / "exercise-5" / "_resources" / "agent-templates" 


def create_audio_mixer(show_context: str):
    role_def = (AGENTS_DIR / "audio-mixer.md").read_text()
    return create_agent(AgentOptions(
        name="AudioMixer",
        instructions=show_context + "\n\n---\n\n" + role_def,
    ))
