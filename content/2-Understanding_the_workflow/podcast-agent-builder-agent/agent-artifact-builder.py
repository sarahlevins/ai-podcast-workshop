"""
Agent Artifact Builder - Console Application

Takes a brief podcast concept, asks the agent to expand it into a
concept + 2 recommended hosts, confirms with the user, then
programmatically fills the role templates and writes the artifacts.
"""

import asyncio
import json
from pathlib import Path

from agent import (
    HOST_FILES,
    HOSTS_DIR,
    OUTPUT_DIR,
    ROLES,
    TEMPLATES_DIR,
    WORKING_DIR,
    ConceptProposal,
    parse_proposal,
    setup_builder_agent,
)


def divider(char="-"):
    print(char * 60)


def heading(title):
    divider("=")
    print(f"  {title}")
    divider("=")


async def stream_text(run) -> str:
    chunks = []
    async for event in run:
        text = getattr(event, "text", None)
        if text:
            print(text, end="", flush=True)
            chunks.append(text)
    print()
    return "".join(chunks)


def render_proposal(p: ConceptProposal):
    print(f"Concept:     {p.podcast_concept}")
    print(f"Title:       {p.podcast_title}")
    print(f"Description: {p.podcast_concept_description}")
    print(f"Hosts:       {', '.join(p.hosts)}")
    if p.host_rationale:
        print(f"Rationale:   {p.host_rationale}")


def write_artifacts(proposal: ConceptProposal) -> list[Path]:
    """Fill the role templates with string replacement and write to disk."""
    unknown = [h for h in proposal.hosts if h not in HOST_FILES]
    if unknown:
        raise ValueError(f"Unknown host id(s): {unknown}")

    host_definitions = "\n\n".join(
        (HOSTS_DIR / HOST_FILES[h]).read_text().rstrip() for h in proposal.hosts
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    written = []
    for role in ROLES:
        template = (TEMPLATES_DIR / f"{role}.txt").read_text()
        filled = (
            template
            .replace("{{PODCAST_CONCEPT}}", proposal.podcast_concept)
            .replace("{{PODCAST_TITLE}}", proposal.podcast_title)
            .replace("{{PODCAST_CONCEPT_DESCRIPTION}}", proposal.podcast_concept_description)
            .replace("{{HOST_DEFINITIONS}}", host_definitions)
        )
        out_path = OUTPUT_DIR / f"{role}.txt"
        out_path.write_text(filled)
        written.append(out_path)
    return written


async def main():
    heading("Agent Artifact Builder")

    brief = input("\nDescribe your podcast concept (one or two sentences): ").strip()
    if not brief:
        print("No concept provided. Exiting.")
        return

    from agent_framework import AgentSession
    agent = setup_builder_agent()
    session = AgentSession()

    prompt = brief
    while True:
        print()
        divider()
        print("Proposing concept and hosts...\n")
        raw = await stream_text(agent.run(prompt, stream=True, session=session))

        try:
            proposal = parse_proposal(raw)
        except (json.JSONDecodeError, KeyError, AttributeError) as e:
            print(f"\nCould not parse agent response ({e}). Asking it to retry...")
            prompt = "Your previous response did not parse. Please respond again with a single ```json fenced block matching the schema."
            continue

        print()
        divider()
        render_proposal(proposal)
        divider()

        answer = input("Approve? (yes / describe changes): ").strip()
        if answer.lower() == "yes":
            break
        prompt = f"The user wants changes: {answer}. Revise and respond again in the same JSON format."

    print()
    heading("Writing artifacts")
    written = write_artifacts(proposal)
    for path in written:
        print(f"  Wrote: {path.relative_to(WORKING_DIR)}")

    print()
    heading("Done")
    print(f"  Location: {OUTPUT_DIR}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
