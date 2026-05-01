"""
Artifact Builder - Console Application

Interactively creates podcast agent artifacts from templates based on a user-provided concept.
Presents each artifact one at a time for review before writing.
"""

import asyncio
from pathlib import Path

from agent_framework import AgentSession
from agent import setup_builder_agent, WORKING_DIR

ROLES = ["producer", "research", "script-writer", "editor", "publisher"]
OUTPUT_DIR = WORKING_DIR / "podcast-agent-artifacts"


async def stream_text(run) -> str:
    """Stream agent response to console and return the full text."""
    chunks = []
    async for event in run:
        text = getattr(event, "text", None)
        if text:
            print(text, end="", flush=True)
            chunks.append(text)
    print()
    return "".join(chunks)


def divider(char="-"):
    print(char * 60)


def heading(title):
    divider("=")
    print(f"  {title}")
    divider("=")


async def main():
    heading("Agent Artifact Builder")

    agent = setup_builder_agent()
    session = AgentSession()

    # Get podcast concept
    concept = input("\nDescribe your podcast concept: ").strip()
    if not concept:
        print("No concept provided. Exiting.")
        return

    # Step 1: Parse concept and propose hosts
    print()
    divider()
    print("Reading host templates and proposing hosts...\n")
    await stream_text(agent.run(
        f"{concept}\n\n"
        "Read the host definition templates and propose 2-3 hosts that best fit this concept. "
        "Show your proposals with one-line justifications. Do not generate any artifacts yet.",
        stream=True,
        session=session,
    ))

    # Step 2: Host approval loop
    while True:
        divider()
        answer = input("Happy with these hosts? (yes / describe changes): ").strip()
        if answer.lower() == "yes":
            break
        print()
        await stream_text(agent.run(answer, stream=True, session=session))

    # Step 3: Generate and review each artifact in order
    for role in ROLES:
        while True:
            print()
            heading(f"Artifact: {role}")
            await stream_text(agent.run(
                f"Generate the {role} artifact by reading the {role} template and filling in "
                f"the three placeholders. Show me the full content. Do not write the file yet.",
                stream=True,
                session=session,
            ))

            divider()
            answer = input(f"Write this {role} artifact? (yes / describe changes): ").strip()

            if answer.lower() == "yes":
                print()
                await stream_text(agent.run(
                    f"Write the {role} artifact to podcast-agent-artifacts/{role}.txt now.",
                    stream=True,
                    session=session,
                ))
                print(f"  Saved: {OUTPUT_DIR / f'{role}.txt'}")
                break
            else:
                print()
                await stream_text(agent.run(
                    f"Revise the {role} artifact: {answer}. Show me the revised content. Do not write the file yet.",
                    stream=True,
                    session=session,
                ))

    print()
    heading("All artifacts complete!")
    print(f"  Location: {OUTPUT_DIR}")
    print()


if __name__ == "__main__":
    asyncio.run(main())
