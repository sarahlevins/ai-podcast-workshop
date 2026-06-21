"""Episode Production Workflow — Section 3.

Multi-phase pipeline that takes an episode brief and produces a source script
plus episode summary. Stops before audio generation (that's Section 4).

Run:
    python content/3-Building_the_workflow/code/episode-production-workflow/workflow.py

Phases:
  1. Research (parallel fan-out)  — Researcher + all Host agents
  1b. Fact-check                  — Fact Checker (depends on Researcher)
  2. Scripting loop (max 3)       — Script Writer → Editor + Hosts → loop
  3. Producer review (max 2)      — Producer → Script Writer → loop
  HITL 1                          — User reviews script (max 3 feedback rounds)
  4. Content pipeline (parallel)  — Show Notes, Metadata, Promo

Outputs (per episode):
  output/episodes/<date>-<slug>/workflow-output/source-script.txt
  output/episodes/<date>-<slug>/workflow-output/episode-summary.md
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

from agents.researcher      import create_researcher      # noqa: E402
from agents.fact_checker    import create_fact_checker    # noqa: E402
from agents.host_agent      import create_host_agents     # noqa: E402
from agents.script_writer   import create_script_writer   # noqa: E402
from agents.editor          import create_editor          # noqa: E402
from agents.producer        import create_producer        # noqa: E402
from agents.show_notes_writer import create_show_notes_writer  # noqa: E402
from agents.metadata_agent  import create_metadata_agent  # noqa: E402
from agents.promo_agent     import create_promo_agent     # noqa: E402

from executors import (  # noqa: E402
    SHOW_CONTEXT_PATH,
    _JSONL_SPAN_EXPORTER,
    _state,
    ContentPipelineFanIn,
    ContentPipelineFanOut,
    ProducerFeedbackRelay,
    ProducerReviewExecutor,
    ResearchFanIn,
    ResearchFanOut,
    SaveExecutor,
    ScriptHITLExecutor,
    ScriptRevisionRelay,
    ScriptReviewFanIn,
    ScriptWriterDispatch,
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

researcher_agent     = create_researcher(SHOW_CONTEXT)
fact_checker_agent   = create_fact_checker(SHOW_CONTEXT)
script_writer_agent  = create_script_writer(SHOW_CONTEXT)
editor_agent         = create_editor(SHOW_CONTEXT)
producer_agent       = create_producer(SHOW_CONTEXT)
show_notes_agent     = create_show_notes_writer(SHOW_CONTEXT)
metadata_agent       = create_metadata_agent(SHOW_CONTEXT)
promo_agent          = create_promo_agent(SHOW_CONTEXT)

host_agents: list[tuple[str, object]] = create_host_agents(SHOW_CONTEXT)
# host_agents is a list of (name, agent) — one per host in show_context.md

# TODO: wire in Music Director after tools are implemented
# Runs in parallel with Audio Engineer; both feed into Post-Production


# ── Build the workflow ────────────────────────────────────────────────────────

def build_workflow():
    # Hosts need SEPARATE executor instances per phase so their responses only
    # flow to the correct fan-in.  Sharing one instance caused Phase-2 host
    # responses to also land in research_fan_in, restarting the research/
    # scripting cascade in parallel with HITL.
    host_research_ids = [f"host_{name}_research" for name, _ in host_agents]
    host_script_ids   = [f"host_{name}_script"   for name, _ in host_agents]

    # Executor instances
    research_fan_out  = ResearchFanOut("research_fan_out", "researcher", host_research_ids)
    research_fan_in   = ResearchFanIn("research_fan_in", "fact_checker")

    researcher_exec   = AgentExecutor(agent=researcher_agent,   id="researcher")
    fact_checker_exec = AgentExecutor(agent=fact_checker_agent, id="fact_checker")

    # Phase-1-only host executors (research)
    host_research_execs = [
        AgentExecutor(agent=agent, id=f"host_{name}_research")
        for name, agent in host_agents
    ]
    # Phase-2-only host executors (script review) — same underlying agents,
    # separate executor IDs so edges don't cross into research_fan_in
    host_script_execs = [
        AgentExecutor(agent=agent, id=f"host_{name}_script")
        for name, agent in host_agents
    ]

    script_writer_exec  = AgentExecutor(agent=script_writer_agent, id="script_writer")
    editor_exec         = AgentExecutor(agent=editor_agent,        id="editor")
    producer_exec       = AgentExecutor(agent=producer_agent,      id="producer")
    show_notes_exec     = AgentExecutor(agent=show_notes_agent,    id="show_notes")
    metadata_exec       = AgentExecutor(agent=metadata_agent,      id="metadata")
    promo_exec          = AgentExecutor(agent=promo_agent,         id="promo")

    sw_dispatch   = ScriptWriterDispatch("sw_dispatch", "editor", host_script_ids, "script_review_fan_in")
    sr_fan_in     = ScriptReviewFanIn("script_review_fan_in", "script_writer", "producer", len(host_agents))
    producer_rev  = ProducerReviewExecutor("producer_review", "script_writer", "script_hitl")

    # HITL executor sends feedback to a dedicated producer instance (producer_hitl)
    # so responses don't accidentally route back through the Phase-3 producer loop.
    producer_hitl_exec = AgentExecutor(agent=producer_agent, id="producer_hitl")
    script_hitl        = ScriptHITLExecutor("script_hitl", "producer_hitl", "content_fan_out")
    producer_fb        = ProducerFeedbackRelay("producer_fb_relay", "script_writer_hitl")
    script_rev_relay   = ScriptRevisionRelay("script_rev_relay", "script_hitl")
    sw_hitl_exec       = AgentExecutor(agent=script_writer_agent, id="script_writer_hitl")

    sn_fan_in  = ContentPipelineFanIn("sn_fan_in",   "show_notes", "save")
    md_fan_in  = ContentPipelineFanIn("md_fan_in",   "metadata",   "save")
    pr_fan_in  = ContentPipelineFanIn("pr_fan_in",   "promo",      "save")

    content_fan_out = ContentPipelineFanOut(
        "content_fan_out", "show_notes", "metadata", "promo", "save"
    )
    save_exec = SaveExecutor("save")

    builder = WorkflowBuilder(start_executor=research_fan_out)

    # Phase 1: research fan-out — research hosts ONLY connect to research_fan_in
    builder.add_edge(research_fan_out, researcher_exec)
    for host_exec in host_research_execs:
        builder.add_edge(research_fan_out, host_exec)
        builder.add_edge(host_exec,        research_fan_in)
    builder.add_edge(researcher_exec,  research_fan_in)
    builder.add_edge(research_fan_in,  fact_checker_exec)

    # Phase 2: scripting loop — script hosts ONLY connect to sr_fan_in
    builder.add_edge(fact_checker_exec, script_writer_exec)
    builder.add_edge(script_writer_exec, sw_dispatch)
    builder.add_edge(sw_dispatch,   editor_exec)
    for host_exec in host_script_execs:
        builder.add_edge(sw_dispatch,   host_exec)
        builder.add_edge(host_exec,     sr_fan_in)
    builder.add_edge(editor_exec,       sr_fan_in)
    builder.add_edge(sr_fan_in,         script_writer_exec)  # revise loop
    builder.add_edge(sr_fan_in,         producer_exec)        # approved path

    # Phase 3: producer review loop
    builder.add_edge(producer_exec,     producer_rev)
    builder.add_edge(producer_rev,      script_writer_exec)   # revise
    builder.add_edge(producer_rev,      script_hitl)          # approved

    # HITL: user feedback → producer_hitl interprets → relay → script_writer_hitl → HITL
    builder.add_edge(script_hitl,       producer_hitl_exec)   # user feedback to dedicated producer
    builder.add_edge(producer_hitl_exec, producer_fb)          # producer interpretation to relay
    builder.add_edge(producer_fb,       sw_hitl_exec)
    builder.add_edge(sw_hitl_exec,      script_rev_relay)     # revised script → relay → HITL
    builder.add_edge(script_rev_relay,  script_hitl)          # back to HITL
    builder.add_edge(script_hitl,       content_fan_out)      # ACCEPT

    # Phase 4: content pipeline
    builder.add_edge(content_fan_out,   show_notes_exec)
    builder.add_edge(content_fan_out,   metadata_exec)
    builder.add_edge(content_fan_out,   promo_exec)
    builder.add_edge(show_notes_exec,   sn_fan_in)
    builder.add_edge(metadata_exec,     md_fan_in)
    builder.add_edge(promo_exec,        pr_fan_in)
    builder.add_edge(sn_fan_in,         save_exec)
    builder.add_edge(md_fan_in,         save_exec)
    builder.add_edge(pr_fan_in,         save_exec)

    return builder.build()


workflow = build_workflow()


def main():
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger = logging.getLogger(__name__)

    parser = argparse.ArgumentParser(description="Episode Production Workflow")
    parser.add_argument("--brief", type=str, default="", help="Episode brief (e.g. 'the numbers and what they mean')")
    args = parser.parse_args()

    _state.cli_brief = args.brief

    # Register our JSONL span exporter BEFORE serve() so it's on the TracerProvider
    # when the dev UI executor adds its own per-request SimpleSpanProcessor.
    # enable_sensitive_data=True attaches full message content (inputs + outputs)
    # to every agent span as events — that's what populates traces.jsonl.
    from agent_framework.observability import configure_otel_providers
    configure_otel_providers(enable_sensitive_data=True, exporters=[_JSONL_SPAN_EXPORTER])

    logger.info("Episode Production Workflow")
    logger.info("DevUI: http://localhost:8090")
    logger.info("Run logs: output/workflow-runs/script/<uuid>/")
    if _state.cli_brief:
        logger.info(f"Brief: {_state.cli_brief!r}  — send any message in the UI to start.")
    else:
        logger.info("Enter an episode brief in the UI to start the pipeline.")

    from agent_framework_devui import serve
    serve(entities=[workflow], port=8090, auto_open=True, instrumentation_enabled=True, auth_enabled=False)


if __name__ == "__main__":
    main()
