"""Podcast Recording Workflow.

A live-conversation recording pipeline. A Researcher first gathers notes on the
topic, then the Recording Producer uses those notes to brief the hosts and open
the session. Hosts then converse utterance-by-utterance while the Producer
manages segment transitions. The raw conversation is assembled into a structured
transcript (schemas/podcast-transcript-v1.json).

Run:
    python content/3-Building_the_workflow/code/episode-production-workflow/podcast-recording.py

Phases:
  0. Research         — Researcher produces notes on the episode topic.
  1. Producer Brief   — Recording Producer reads research, produces segment rundown + opening question.
  2. Recording Loop   — Hosts converse utterance-by-utterance:
                          a. Speaking host produces one ---UTTERANCE--- block.
                          b. Listening host immediately reacts (or passes).
                          c. Every N utterances, Producer checks in and may transition segments.
  3. Assembly         — Transcript Assembler converts the raw log to podcast-transcript-v1.json.

Outputs:
  output/episodes/<date>-<slug>/workflow-output/transcript.json
  output/workflow-runs/recording/<uuid>/recording/full_recording_log.md
"""

import logging
import sys
from pathlib import Path

# ── Path & env setup ──────────────────────────────────────────────────────────

WORKSPACE = Path(__file__).resolve().parents[4]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(WORKSPACE / ".env")

from agent_framework import AgentExecutor, WorkflowBuilder  # noqa: E402

from agents.host_agent           import create_recording_host_agents  # noqa: E402
from agents.recording_producer   import create_recording_producer     # noqa: E402
from agents.researcher           import create_researcher             # noqa: E402
from agents.transcript_assembler import create_transcript_assembler  # noqa: E402

from executors import (  # noqa: E402
    SHOW_CONTEXT_PATH,
    _JSONL_SPAN_EXPORTER,
    _state,
)
from executors.recording import (  # noqa: E402
    RecordingResearchExecutor,
    RecordingResearchRelay,
    HostResearchDigestExecutor,
    HostResearchDigestRelay,
    RecordingBriefExecutor,
    RecordingBriefRelay,
    HostRelay,
    ChatRoomProducerRelay,
    ChatRoomExecutor,
    TranscriptAssemblyExecutor,
    EpisodeBriefInput,
    _rec,
)

# ── Show context ──────────────────────────────────────────────────────────────

if not SHOW_CONTEXT_PATH.exists():
    raise FileNotFoundError(
        f"{SHOW_CONTEXT_PATH} not found.\n"
        "Run the Show Setup Workflow first:\n"
        "  python content/2-Understanding_the_workflow/exercise/chat.py"
    )

SHOW_CONTEXT = SHOW_CONTEXT_PATH.read_text()

# ── Agents ────────────────────────────────────────────────────────────────────

researcher_agent           = create_researcher(SHOW_CONTEXT)
recording_producer_agent   = create_recording_producer(SHOW_CONTEXT)
transcript_assembler_agent = create_transcript_assembler(SHOW_CONTEXT)

recording_host_agents: list[tuple[str, object]] = create_recording_host_agents(SHOW_CONTEXT)
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
    research_relay  = RecordingResearchRelay("research_relay", "host_a_digest_exec")

    # ── Phase 0.5: host research digests (sequential: A then B) ─────────────
    host_a_digest_exec       = HostResearchDigestExecutor(
        "host_a_digest_exec", host_a_id, host_a_name, "host_a_digest_agent")
    host_a_digest_agent_exec = AgentExecutor(agent=host_a_agent, id="host_a_digest_agent")
    host_a_digest_relay      = HostResearchDigestRelay(
        "host_a_digest_relay", host_a_id, "host_b_digest_exec")

    host_b_digest_exec       = HostResearchDigestExecutor(
        "host_b_digest_exec", host_b_id, host_b_name, "host_b_digest_agent")
    host_b_digest_agent_exec = AgentExecutor(agent=host_b_agent, id="host_b_digest_agent")
    host_b_digest_relay      = HostResearchDigestRelay(
        "host_b_digest_relay", host_b_id, "recording_brief")

    # ── Phase 1: producer brief ──────────────────────────────────────────────
    brief_exec    = RecordingBriefExecutor("recording_brief", "recording_producer", "brief_relay")
    producer_exec = AgentExecutor(agent=recording_producer_agent, id="recording_producer")
    brief_relay   = RecordingBriefRelay("brief_relay", "chat_room", [host_a_id, host_b_id])

    # ── Phase 2: group-chat recording loop ───────────────────────────────────
    host_a_exec = AgentExecutor(agent=host_a_agent, id=host_a_id)
    host_b_exec = AgentExecutor(agent=host_b_agent, id=host_b_id)

    # One HostRelay per host: wraps AgentExecutorResponse → HostUtterance
    host_a_relay = HostRelay("host_a_relay", host_a_id, "chat_room")
    host_b_relay = HostRelay("host_b_relay", host_b_id, "chat_room")

    # Separate producer instance for check-ins (so its responses flow to the
    # relay, not back into brief_relay's edge)
    producer_checkin_exec = AgentExecutor(agent=recording_producer_agent, id="producer_checkin")
    producer_relay        = ChatRoomProducerRelay("producer_relay", "chat_room")

    chat_room = ChatRoomExecutor(
        id="chat_room",
        host_a_id=host_a_id,
        host_b_id=host_b_id,
        host_a_name=host_a_name,
        host_b_name=host_b_name,
        producer_checkin_id="producer_checkin",
        assembly_id="transcript_assembler",  # the AI agent, not the save executor
    )

    # ── Phase 3: transcript assembly ─────────────────────────────────────────
    assembler_exec = AgentExecutor(agent=transcript_assembler_agent, id="transcript_assembler")
    assembly_exec  = TranscriptAssemblyExecutor("transcript_assembly")

    builder = WorkflowBuilder(start_executor=research_exec, max_iterations=500)

    # Phase 0
    builder.add_edge(research_exec,   researcher_exec)
    builder.add_edge(researcher_exec, research_relay)

    # Phase 0.5: host digests (A → B → brief)
    builder.add_edge(research_relay,          host_a_digest_exec)
    builder.add_edge(host_a_digest_exec,      host_a_digest_agent_exec)
    builder.add_edge(host_a_digest_agent_exec, host_a_digest_relay)
    builder.add_edge(host_a_digest_relay,     host_b_digest_exec)
    builder.add_edge(host_b_digest_exec,      host_b_digest_agent_exec)
    builder.add_edge(host_b_digest_agent_exec, host_b_digest_relay)
    builder.add_edge(host_b_digest_relay,     brief_exec)

    # Phase 1
    builder.add_edge(brief_exec,    producer_exec)
    builder.add_edge(producer_exec, brief_relay)
    builder.add_edge(brief_relay,   chat_room)       # RecordingTurn → ChatRoom.start

    # Phase 2: chat_room ↔ hosts (via relays); chat_room → producer_checkin → relay → chat_room
    builder.add_edge(chat_room,              host_a_exec)
    builder.add_edge(chat_room,              host_b_exec)
    builder.add_edge(host_a_exec,            host_a_relay)
    builder.add_edge(host_b_exec,            host_b_relay)
    builder.add_edge(host_a_relay,           chat_room)        # HostUtterance
    builder.add_edge(host_b_relay,           chat_room)        # HostUtterance
    builder.add_edge(chat_room,              producer_checkin_exec)
    builder.add_edge(producer_checkin_exec,  producer_relay)
    builder.add_edge(producer_relay,         chat_room)        # ProducerDirection

    # Phase 3
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


if __name__ == "__main__":
    main()
