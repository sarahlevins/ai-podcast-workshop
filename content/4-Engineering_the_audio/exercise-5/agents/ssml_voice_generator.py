"""SSML Voice Generator agent — loads output/agents/ssml-voice-generator.md.

Converts transcript.json to MAI-2 SSML format.
"""

import sys
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[4]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from utils.agents import create_agent, AgentOptions  # noqa: E402

AGENTS_DIR = WORKSPACE / "4-Engineering_the_audio" / "exercise-5" / "_resources" / "agent-templates" 

def create_ssml_voice_generator(show_context: str):
    role_def = (AGENTS_DIR / "ssml-voice-generator.md").read_text()
    return create_agent(AgentOptions(
        name="SSMLVoiceGenerator",
        instructions=show_context + "\n\n---\n\n" + role_def,
    ))
