"""Music Director agent — loads output/agents/music-director.md.

Plans music and SFX cues for an episode, selecting from the embedded catalog.
"""

import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[4]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from utils.agents import create_agent, AgentOptions  # noqa: E402

AGENTS_DIR = WORKSPACE / "4-Engineering_the_audio" / "exercise-5" / "_resources" / "agent-templates" 

def create_music_director(show_context: str):
    role_def = (AGENTS_DIR / "music-director.md").read_text()
    return create_agent(AgentOptions(
        name="MusicDirector",
        instructions=show_context + "\n\n---\n\n" + role_def,
    ))
