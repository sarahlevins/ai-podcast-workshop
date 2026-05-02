"""Artifact builder agent that reads templates and writes filled-in artifacts."""

import os
from pathlib import Path
from typing import Annotated

from dotenv import load_dotenv
from pydantic import Field

from utils.agents import create_agent, AgentOptions

load_dotenv()

# All file operations are scoped to this directory
WORKING_DIR = Path(__file__).resolve().parent.parent

# Load the system prompt from the instructions file in the same directory as this module
INSTRUCTIONS = (Path(__file__).resolve().parent / "agent-artifact-builder.txt").read_text()


def _resolve(relative_path: str) -> Path:
    """Resolve a relative path and ensure it stays inside WORKING_DIR."""
    resolved = (WORKING_DIR / relative_path).resolve()
    if not str(resolved).startswith(str(WORKING_DIR)):
        raise ValueError(f"Path must be inside {WORKING_DIR}")
    return resolved


def read_file(
    path: Annotated[str, Field(description="Relative path to read, e.g. 'templates/agent-instruction-templates/producer.txt'")],
) -> str:
    """Read a file's contents. Path is relative to content/2-Understanding_the_workflow/."""
    target = _resolve(path)
    if not target.is_file():
        return f"Error: {path} not found"
    return target.read_text()


def list_directory(
    path: Annotated[str, Field(description="Relative directory path, e.g. 'templates/host-definition-templates'")] = ".",
) -> str:
    """List files and directories. Path is relative to content/2-Understanding_the_workflow/."""
    target = _resolve(path)
    if not target.is_dir():
        return f"Error: {path} is not a directory"
    entries = sorted(target.iterdir())
    return "\n".join(
        f"{'[dir]  ' if e.is_dir() else '[file] '}{e.relative_to(WORKING_DIR)}"
        for e in entries
        if not e.name.startswith("__")
    )


def write_file(
    path: Annotated[str, Field(description="Relative path to write, e.g. 'podcast-agent-artifacts/producer.txt'")],
    content: Annotated[str, Field(description="File content to write")],
) -> str:
    """Write content to a file, creating parent directories if needed."""
    target = _resolve(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    return f"Wrote {target.relative_to(WORKING_DIR)}"


def setup_builder_agent():
    """Create the artifact builder agent with file tools."""
    return create_agent(AgentOptions(
        name="ArtifactBuilder",
        instructions=INSTRUCTIONS,
        tools=[read_file, list_directory, write_file],
    ))
