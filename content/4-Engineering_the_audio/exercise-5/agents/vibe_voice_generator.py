"""VibeVoice Script Generator agent — loads output/agents/vibe-voice-generator.md.

Converts transcript.json to VibeVoice 7B script format.
"""

import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[4]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from utils.agents import create_agent, AgentOptions  # noqa: E402

AGENTS_DIR = WORKSPACE / "content" / "4-Engineering_the_audio" / "exercise-5" / "_resources" / "agent-templates" 

def create_vibe_voice_generator(show_context: str):
    role_def = (AGENTS_DIR / "vibe-voice-generator.md").read_text()
    return create_agent(AgentOptions(
        name="VibeVoiceGenerator",
        instructions=show_context + "\n\n---\n\n" + role_def,
    ))
