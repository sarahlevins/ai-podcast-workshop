"""Show Setup Workflow — Section 2, Exercise 1.

A CLI conversation that interviews you about your podcast show, then writes
output/show_context.md and seeds all output/agents/*.md files.

Run:
    python content/2-Developing_the_concept/exercise-1/chat.py

Flow:
  1. Show Concept Agent asks one question at a time.
  2. You respond freely in the terminal.
  3. Type CONFIRM (case-insensitive) when you are happy with the concept.
  4. The agent emits structured JSON; the script writes your config files.
  5. Cycle guard: max 30 turns before forced CONFIRM.
"""

import asyncio
import json
import sys
from pathlib import Path

# ── Path & env setup ──────────────────────────────────────────────────────────

WORKSPACE = Path(__file__).resolve().parents[3]
_resources = Path(__file__).parent / "_resources"
sys.path.insert(0, str(WORKSPACE))
sys.path.insert(0, str(_resources))
sys.path.insert(0, str(_resources / "voice"))

from list_voice_options import list_voice_options # type: ignore
from show_config import parse_show_config, save_config # type: ignore
from utils import load_env, create_agent, AgentOptions
load_env()

# ── Constants ─────────────────────────────────────────────────────────────────

MAX_TURNS = 30
DIVIDER   = "─" * 60

# ── CLI conversation loop ─────────────────────────────────────────────────────

async def stream_response(agent, message: str, session) -> str:
    """Send a message, stream the response to stdout, and return the full text."""
    print(f"\n\033[1;36mAgent:\033[0m ", end="", flush=True)
    stream = agent.run(message, session=session, stream=True)
    full_text = ""
    async for update in stream:
        chunk = update.text or ""
        print(chunk, end="", flush=True)
        full_text += chunk
    print()
    return full_text


async def main() -> None:
    print(DIVIDER)
    print("  Show Setup — Section 2, Exercise 1")
    print("  Type your answers below. Type CONFIRM when done.")
    print(DIVIDER)

    agent_def = (Path(__file__).parent / "show-concept-agent.md").read_text()
    agent = create_agent(AgentOptions(
        name="ShowConceptAgent",
        instructions=agent_def,
        tools=[list_voice_options],
    ))
    session = agent.create_session()

    await stream_response(
        agent,
        "Please start the show setup interview. Introduce yourself briefly and ask your first question.",
        session,
    )

    turn = 0
    while turn < MAX_TURNS:
        try:
            user_input = input(f"\n\033[1;33mYou:\033[0m ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nInterrupted. Exiting without saving.")
            return

        if not user_input:
            continue

        turn += 1

        if user_input.upper() == "CONFIRM" or turn >= MAX_TURNS:
            if turn >= MAX_TURNS and user_input.upper() != "CONFIRM":
                print(f"\n[Reached {MAX_TURNS}-turn limit — finalising automatically.]")

            print(f"\n{DIVIDER}")
            print("  Generating your show configuration…")
            print(DIVIDER)

            json_text = await stream_response(
                agent,
                "The user has confirmed they are happy with the show concept. "
                "Output the final show configuration as a single JSON object in a "
                "```json fenced block, following the schema in your instructions. "
                "No surrounding text.",
                session,
            )

            for attempt in range(3):
                try:
                    cfg = parse_show_config(json_text)
                    break
                except (json.JSONDecodeError, KeyError) as e:
                    if attempt == 2:
                        print(f"\nCould not parse JSON after 3 attempts: {e}")
                        print("Raw output:\n", json_text)
                        return
                    print(f"\n[JSON parse error: {e} — asking agent to retry…]")
                    json_text = await stream_response(
                        agent,
                        f"The JSON could not be parsed ({e}). Please output ONLY a single "
                        "```json block with the show configuration and nothing else.",
                        session,
                    )

            ctx_path, agent_paths = save_config(cfg)

            print(f"\n{DIVIDER}")
            print(f"  Show configured: {cfg.show_name}")
            print(f"  Hosts: {', '.join(h.name for h in cfg.hosts)}")
            print()
            print("  Files written:")
            print(f"    {ctx_path.relative_to(WORKSPACE)}")
            for p in agent_paths:
                print(f"    {p}")
            print(DIVIDER)
            print()
            print("Next steps:")
            print("  1. Review output/show_context.md — your show concept.")
            print("  2. Review output/agents/host-*.md — your host personalities.")
            print("  3. Edit either file before moving on — changes feed directly into Section 3.")
            print("  4. Run the Episode Production Workflow (Section 3).")
            return

        await stream_response(agent, user_input, session)


if __name__ == "__main__":
    asyncio.run(main())
