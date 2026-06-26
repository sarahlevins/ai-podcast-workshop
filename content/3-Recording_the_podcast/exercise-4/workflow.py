"""Podcast Recording Workflow.

A live-conversation recording pipeline. A Researcher first gathers notes on the
topic, then the Recording Producer uses those notes to brief the hosts and open
the session. Hosts then converse utterance-by-utterance while the Producer
manages segment transitions. The raw conversation is assembled into a structured
transcript (utils/podcast-transcript-v1.json).

Run:
    python content/3-Recording_the_podcast/exercise-4/workflow.py

Phases:
  0. Research         — Researcher produces notes on the episode topic.
  1. Host Digests     — Each host reads the research and builds their personal reference.
  2. Producer Brief   — Recording Producer reads research, produces segment rundown + opening question.
  3. Recording Loop   — Hosts converse utterance-by-utterance:
                          a. Speaking host produces one ---UTTERANCE--- block.
                          b. Listening host immediately reacts (or passes).
                          c. Every N utterances, Producer checks in and may transition segments.
  4. Assembly         — Transcript Assembler converts the raw log to podcast-transcript-v1.json.

Outputs:
  output/episodes/<date>-<slug>/transcript.json
  output/episodes/<date>-<slug>/recording-log.md
"""

import logging
import re
import sys
from pathlib import Path

# ── Path & env setup ──────────────────────────────────────────────────────────

WORKSPACE = Path(__file__).resolve().parents[3]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

RESOURCES_DIR = Path(__file__).resolve().parents[1] / "_resources"
if str(RESOURCES_DIR) not in sys.path:
    sys.path.insert(0, str(RESOURCES_DIR))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(WORKSPACE / ".env")

from agent_framework import AgentExecutor, WorkflowBuilder  # noqa: E402
from utils.agents import create_agent, AgentOptions  # noqa: E402
from utils import summarize_token_usage_trace  # noqa: E402

from executors import SHOW_CONTEXT_PATH, _state  # noqa: E402
from executors.recording import (  # noqa: E402
    RecordingResearchExecutor,
    RecordingResearchRelay,
    HostResearchDigestExecutor,
    HostResearchDigestRelay,
    HostDigestFanIn,
    RecordingBriefExecutor,
    RecordingBriefRelay,
    HostRelay,
    ChatRoomProducerRelay,
    ChatRoomExecutor,
    TranscriptAssemblyExecutor,
)

# ── Show context ──────────────────────────────────────────────────────────────

if not SHOW_CONTEXT_PATH.exists():
    raise FileNotFoundError(
        f"{SHOW_CONTEXT_PATH} not found.\n"
        "Run the Show Setup Workflow first:\n"
        "  python content/2-Developing_the_concept/exercise-1/chat.py"
    )

SHOW_CONTEXT = SHOW_CONTEXT_PATH.read_text()

# ── Agent templates ───────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parents[3]
TEMPLATE_DIR = Path(__file__).parent / "_resources" / "agent-templates"
AGENTS_DIR = PROJECT_ROOT / "output" / "agents"

# ── Helpers ───────────────────────────────────────────────────────────

def _show_context_para(show_context: str) -> str:
    """Extract a short summary paragraph from show_context.md for agent instructions."""
    tagline_match = re.search(r"\*\*Name / Tagline:\*\*\s*(.+)", show_context)
    format_match = re.search(r"\*\*Format:\*\*\s*(.+)", show_context)
    tone_match = re.search(r"\*\*Tone:\*\*\s*(.+)", show_context)

    hosts_match = re.search(
        r"^## Hosts\s*\n(.*?)(?=^## |\Z)", show_context, re.MULTILINE | re.DOTALL
    )
    host_names = (
        [
            s.strip()
            for s in re.split(r"^### (.+)$", hosts_match.group(1), flags=re.MULTILINE)[1::2]
            if s.strip()
        ]
        if hosts_match
        else []
    )

    segments_match = re.search(
        r"^## Recurring Segments\s*\n(.*?)(?=^## |\Z)", show_context, re.MULTILINE | re.DOTALL
    )
    segments = (
        [
            line.lstrip("- ").split("(")[0].strip()
            for line in segments_match.group(1).strip().splitlines()
            if line.strip().startswith("-")
        ]
        if segments_match
        else []
    )

    lines = []
    if tagline_match:
        lines.append(f"**Show:** {tagline_match.group(1).strip()}")
    if host_names:
        lines.append(f"**Hosts:** {' and '.join(host_names)}")
    if format_match:
        lines.append(f"**Format:** {format_match.group(1).strip()}")
    if segments:
        lines.append(f"**Segments:** {', '.join(segments)}")
    if tone_match:
        lines.append(f"**Tone:** {tone_match.group(1).strip()}")
    lines.append(f"**Full context:** {SHOW_CONTEXT_PATH}")

    return "\n".join(lines)


SHOW_CONTEXT_PARA = _show_context_para(SHOW_CONTEXT)


def _host_slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _parse_host_names(show_context: str) -> list[str]:
    hosts_match = re.search(
        r"^## Hosts\s*\n(.*?)(?=^## |\Z)", show_context, re.MULTILINE | re.DOTALL
    )
    if not hosts_match:
        return []
    return [
        s.strip()
        for s in re.split(r"^### (.+)$", hosts_match.group(1), flags=re.MULTILINE)[1::2]
        if s.strip()
    ]


def _load_agent(template_name: str, agent_name: str):
    """Create an agent from a template file, prepending the show context summary."""
    template = (TEMPLATE_DIR / template_name).read_text()
    return create_agent(AgentOptions(
        name=agent_name,
        instructions=SHOW_CONTEXT_PARA + "\n\n---\n\n" + template,
    ))


def _prepare_recording_host_files() -> None:
    """Copy host-*.md → host-*-recording.md, replacing ## Your role in the workflow onwards
    with the recording-host.md template."""
    recording_template = (TEMPLATE_DIR / "recording-host.md").read_text()
    source_files = [
        f for f in AGENTS_DIR.glob("host-*.md")
        if not f.stem.endswith("-recording")
    ]
    if not source_files:
        raise FileNotFoundError(
            f"No host agent files found in {AGENTS_DIR}.\n"
            "Run the Show Setup Workflow first:\n"
            "  python content/2-Developing_the_concept/exercise-1/chat.py"
        )
    for src in source_files:
        content = src.read_text()
        cut = content.find("\n## Your role in the workflow")
        base = content[:cut] if cut != -1 else content.rstrip()
        recording_content = base + "\n\n" + recording_template
        slug = src.stem[len("host-"):]
        dest = AGENTS_DIR / f"host-{slug}-recording.md"
        dest.write_text(recording_content)


def _create_recording_host_agents() -> list[tuple[str, object]]:
    """Return (name, agent) pairs for each host defined in show_context.md."""
    conversation_style_path = AGENTS_DIR / "conversation-style.md"
    conversation_style = (
        "\n\n---\n\n" + conversation_style_path.read_text()
        if conversation_style_path.exists()
        else ""
    )
    agents = []
    for name in _parse_host_names(SHOW_CONTEXT):
        slug = _host_slug(name)
        host_file = AGENTS_DIR / f"host-{slug}-recording.md"
        if not host_file.exists():
            raise FileNotFoundError(
                f"Recording host file not found: {host_file}\n"
                "Re-run the show setup workflow to regenerate output/agents/."
            )
        instructions = SHOW_CONTEXT_PARA + "\n\n---\n\n" + host_file.read_text() + conversation_style
        agents.append((name, create_agent(AgentOptions(
            name=f"Host_{name}_Recording",
            instructions=instructions,
        ))))
    return agents

_prepare_recording_host_files()

# ── Agents ────────────────────────────────────────────────────────────────────

researcher_agent           = _load_agent("researcher.md",           "Researcher")
recording_producer_agent   = _load_agent("recording-producer.md",   "RecordingProducer")
transcript_assembler_agent = _load_agent("transcript-assembler.md", "TranscriptAssembler")

recording_host_agents: list[tuple[str, object]] = _create_recording_host_agents()
# recording_host_agents is [(name, agent), ...] — one per host in show_context.md

# ── Build the workflow ────────────────────────────────────────────────────────

def build_workflow():
    host_a_name, host_a_agent = recording_host_agents[0]
    host_b_name, host_b_agent = recording_host_agents[1]

    host_a_id = f"host_{host_a_name}_rec"
    host_b_id = f"host_{host_b_name}_rec"

    # ── Phase 0: research ────────────────────────────────────────────────────
    research_exec   = RecordingResearchExecutor("recording_research", "researcher")
    researcher_exec = AgentExecutor(agent=researcher_agent, id="researcher")
    research_relay  = RecordingResearchRelay(
        "research_relay", ["host_a_digest_exec", "host_b_digest_exec"])

    # ── Phase 1: host research digests (parallel) ────────────────────────────
    host_a_digest_exec       = HostResearchDigestExecutor(
        "host_a_digest_exec", host_a_id, host_a_name, "host_a_digest_agent")
    host_a_digest_agent_exec = AgentExecutor(agent=host_a_agent, id="host_a_digest_agent") # type: ignore
    host_a_digest_relay      = HostResearchDigestRelay(
        "host_a_digest_relay", host_a_id, "digest_fanin")

    host_b_digest_exec       = HostResearchDigestExecutor(
        "host_b_digest_exec", host_b_id, host_b_name, "host_b_digest_agent")
    host_b_digest_agent_exec = AgentExecutor(agent=host_b_agent, id="host_b_digest_agent") # type: ignore
    host_b_digest_relay      = HostResearchDigestRelay(
        "host_b_digest_relay", host_b_id, "digest_fanin")

    digest_fanin = HostDigestFanIn("digest_fanin", 2, "recording_brief")

    # ── Phase 2: producer brief ──────────────────────────────────────────────
    brief_exec    = RecordingBriefExecutor("recording_brief", "recording_producer", "brief_relay")
    producer_exec = AgentExecutor(agent=recording_producer_agent, id="recording_producer")
    brief_relay   = RecordingBriefRelay("brief_relay", "chat_room", [host_a_id, host_b_id])

    # ── Phase 3: group-chat recording loop ───────────────────────────────────
    host_a_exec  = AgentExecutor(agent=host_a_agent, id=host_a_id) # type: ignore
    host_b_exec  = AgentExecutor(agent=host_b_agent, id=host_b_id) # type: ignore
    host_a_relay = HostRelay("host_a_relay", host_a_id, "chat_room")
    host_b_relay = HostRelay("host_b_relay", host_b_id, "chat_room")

    producer_checkin_exec = AgentExecutor(agent=recording_producer_agent, id="producer_checkin")
    producer_relay        = ChatRoomProducerRelay("producer_relay", "chat_room")

    chat_room = ChatRoomExecutor(
        id="chat_room",
        host_a_id=host_a_id,
        host_b_id=host_b_id,
        host_a_name=host_a_name,
        host_b_name=host_b_name,
        producer_checkin_id="producer_checkin",
        assembly_id="transcript_assembler",
    )

    # ── Phase 4: transcript assembly ─────────────────────────────────────────
    assembler_exec = AgentExecutor(agent=transcript_assembler_agent, id="transcript_assembler")
    assembly_exec  = TranscriptAssemblyExecutor("transcript_assembly")

    builder = WorkflowBuilder(start_executor=research_exec, max_iterations=500)

    # Phase 0: research
    builder.add_edge(research_exec,   researcher_exec)
    builder.add_edge(researcher_exec, research_relay)

    # Phase 1: host digests in parallel → fan-in → brief
    builder.add_edge(research_relay,           host_a_digest_exec)
    builder.add_edge(research_relay,           host_b_digest_exec)
    builder.add_edge(host_a_digest_exec,       host_a_digest_agent_exec)
    builder.add_edge(host_a_digest_agent_exec, host_a_digest_relay)
    builder.add_edge(host_b_digest_exec,       host_b_digest_agent_exec)
    builder.add_edge(host_b_digest_agent_exec, host_b_digest_relay)
    builder.add_edge(host_a_digest_relay,      digest_fanin)
    builder.add_edge(host_b_digest_relay,      digest_fanin)
    builder.add_edge(digest_fanin,             brief_exec)

    # Phase 2: producer brief
    builder.add_edge(brief_exec,    producer_exec)
    builder.add_edge(producer_exec, brief_relay)
    builder.add_edge(brief_relay,   chat_room)

    # Phase 3: chat room ↔ hosts; chat room → producer check-in → chat room
    builder.add_edge(chat_room,             host_a_exec)
    builder.add_edge(chat_room,             host_b_exec)
    builder.add_edge(host_a_exec,           host_a_relay)
    builder.add_edge(host_b_exec,           host_b_relay)
    builder.add_edge(host_a_relay,          chat_room)
    builder.add_edge(host_b_relay,          chat_room)
    builder.add_edge(chat_room,             producer_checkin_exec)
    builder.add_edge(producer_checkin_exec, producer_relay)
    builder.add_edge(producer_relay,        chat_room)

    # Phase 4: assembly
    builder.add_edge(chat_room,     assembler_exec)
    builder.add_edge(assembler_exec, assembly_exec)

    return builder.build()


workflow = build_workflow()


def main():
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger = logging.getLogger(__name__)

    parser = argparse.ArgumentParser(description="Podcast Recording Workflow")
    parser.add_argument("--brief", type=str, default="", help="Episode brief (e.g. 'the season 3 turning point')")
    args = parser.parse_args()

    _state.cli_brief = args.brief

    from agent_framework.observability import configure_otel_providers
    from executors.state import _JSONL_SPAN_EXPORTER  # noqa: F401
    configure_otel_providers(enable_sensitive_data=True, exporters=[_JSONL_SPAN_EXPORTER])

    logger.info("Podcast Recording Workflow")
    logger.info("DevUI: http://localhost:8091")
    if _state.cli_brief:
        logger.info(f"Brief: {_state.cli_brief!r}  — send any message in the UI to start.")
    else:
        logger.info("Enter an episode brief in the UI to start the recording.")

    from agent_framework_devui import serve
    serve(entities=[workflow], port=8091, auto_open=True, instrumentation_enabled=True, auth_enabled=False)

    trace_path = _state.episode_dir / "recording-artifacts" / "traces.jsonl"
    if trace_path.exists():
        totals = summarize_token_usage_trace(trace_path)
        if totals:
            logger.info("Token usage summary for %s:", _state.episode_dir.name)
            logger.info("  input tokens:      %d", totals["input_tokens"])
            logger.info("  output tokens:     %d", totals["output_tokens"])
            logger.info("  total tokens:      %d", totals["total_tokens"])
            logger.info("  spans with usage:  %d", totals["spans_with_usage"])
        else:
            logger.info("No token usage data found in %s", trace_path)
    else:
        logger.info("No traces.jsonl found — token summary unavailable.")


if __name__ == "__main__":
    main()
