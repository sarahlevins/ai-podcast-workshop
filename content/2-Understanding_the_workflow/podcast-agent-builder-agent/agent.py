"""Concept builder agent: expands a brief into a podcast concept + 2 hosts.

Also exports the constants and helpers shared between the CLI app and the
workflow (template paths, host id -> file map, JSON parser).
"""

import json
import re
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from utils.agents import create_agent, AgentOptions

load_dotenv()

# Workshop content root for this lesson.
WORKING_DIR = Path(__file__).resolve().parent.parent

INSTRUCTIONS = (Path(__file__).resolve().parent / "agent-artifact-builder.txt").read_text()

ROLES = ["producer", "research", "script-writer", "editor", "publisher"]
TEMPLATES_DIR = WORKING_DIR / "templates" / "agent-instruction-templates"
HOSTS_DIR = WORKING_DIR / "templates" / "host-definition-templates"
OUTPUT_DIR = WORKING_DIR / "podcast-agent-artifacts"

HOST_FILES = {
    "jay": "jay-comic-relief.txt",
    "ken": "ken-expert.txt",
    "lucy": "lucy-curious-host.txt",
    "maya": "maya-skeptic.txt",
    "priya": "priya-practitioner.txt",
    "sam": "sam-storyteller.txt",
}


@dataclass
class ConceptProposal:
    """The agent's proposed concept, parsed from its JSON response."""
    podcast_concept: str
    podcast_title: str
    podcast_concept_description: str
    hosts: list[str]
    host_rationale: str = ""


def parse_proposal(text: str) -> ConceptProposal:
    """Extract the JSON block from the agent's response and parse it."""
    match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    raw = match.group(1) if match else text
    data = json.loads(raw)
    return ConceptProposal(
        podcast_concept=data["podcast_concept"],
        podcast_title=data["podcast_title"],
        podcast_concept_description=data["podcast_concept_description"],
        hosts=[h.lower().strip() for h in data["hosts"]],
        host_rationale=data.get("host_rationale", ""),
    )


def setup_builder_agent():
    """Create the concept builder agent. No tools — pure brainstorming."""
    return create_agent(AgentOptions(
        name="ConceptBuilder",
        instructions=INSTRUCTIONS,
    ))
