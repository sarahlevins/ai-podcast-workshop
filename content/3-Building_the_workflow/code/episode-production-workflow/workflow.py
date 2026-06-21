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

import asyncio
import re
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

# ── Path & env setup ──────────────────────────────────────────────────────────

WORKSPACE = Path(__file__).resolve().parents[4]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from dotenv import load_dotenv  # noqa: E402
load_dotenv(WORKSPACE / ".env")

from agent_framework import (  # noqa: E402
    AgentExecutor,
    AgentExecutorRequest,
    AgentExecutorResponse,
    Executor,
    Message,
    WorkflowBuilder,
    WorkflowContext,
    handler,
    response_handler,
)
from utils.agents import create_agent, AgentOptions  # noqa: E402

from agents.researcher      import create_researcher      # noqa: E402
from agents.fact_checker    import create_fact_checker    # noqa: E402
from agents.host_agent      import create_host_agents     # noqa: E402
from agents.script_writer   import create_script_writer   # noqa: E402
from agents.editor          import create_editor          # noqa: E402
from agents.producer        import create_producer        # noqa: E402
from agents.show_notes_writer import create_show_notes_writer  # noqa: E402
from agents.metadata_agent  import create_metadata_agent  # noqa: E402
from agents.promo_agent     import create_promo_agent     # noqa: E402

# ── Show context ──────────────────────────────────────────────────────────────

SHOW_CONTEXT_PATH = WORKSPACE / "output" / "show_context.md"

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

# ── Shared pipeline state ─────────────────────────────────────────────────────

@dataclass
class PipelineState:
    brief: str = ""
    slug: str = ""
    episode_dir: Path = field(default_factory=Path)

    # Research accumulation
    research_results: list[str] = field(default_factory=list)
    research_needed: int = 0   # how many agents must report before fan-in completes

    # Scripting loop
    script: str = ""
    script_cycle: int = 0
    MAX_SCRIPT_CYCLES: int = 3

    # Producer loop
    producer_cycle: int = 0
    MAX_PRODUCER_CYCLES: int = 2

    # HITL
    hitl_rounds: int = 0
    MAX_HITL_ROUNDS: int = 3

    # Content pipeline accumulation
    content_results: dict[str, str] = field(default_factory=dict)
    content_needed: int = 3   # show notes + metadata + promo


_state = PipelineState()


# ── Human-in-the-loop request types ──────────────────────────────────────────

@dataclass
class ScriptReviewRequest:
    script: str
    round: int
    prompt: str = (
        "Review the script.\n"
        "  • Type 'ACCEPT' to approve it and move to the content pipeline.\n"
        "  • Or describe what you want changed (max 3 rounds)."
    )


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_episode_dir(brief: str) -> Path:
    slug = re.sub(r"[^a-z0-9]+", "-", brief.lower().strip())[:50].strip("-")
    today = date.today().isoformat()
    ep_dir = WORKSPACE / "output" / "episodes" / f"{today}-{slug}"
    (ep_dir / "workflow-output").mkdir(parents=True, exist_ok=True)
    (ep_dir / "artifacts" / "vibevoice").mkdir(parents=True, exist_ok=True)
    (ep_dir / "artifacts" / "azure-ssml").mkdir(parents=True, exist_ok=True)
    (ep_dir / "artifacts" / "mai2").mkdir(parents=True, exist_ok=True)
    (ep_dir / "audio" / "segments").mkdir(parents=True, exist_ok=True)
    return ep_dir


def editor_approved(editor_text: str) -> bool:
    """Returns True if the Editor's response contains APPROVED."""
    return bool(re.search(r"\bAPPROVED\b", editor_text, re.IGNORECASE))


def producer_approved(producer_text: str) -> bool:
    """Returns True if the Producer's response signals approval."""
    return bool(re.search(r"\bAPPROVED\b", producer_text, re.IGNORECASE))


def append_episode_history(brief: str, script: str) -> None:
    """Append a brief episode history entry to show_context.md."""
    today = date.today().isoformat()
    entry = f"\n### {today} — {brief[:60]}\n- **Topic / Angle:** {brief}\n"
    with open(SHOW_CONTEXT_PATH, "a") as f:
        f.write(entry)


# ── Phase 1: Research fan-out / fan-in ───────────────────────────────────────

class ResearchFanOut(Executor):
    """Sends the episode brief to the Researcher and all Host agents in parallel.

    This is the fan-out step: one input → N concurrent research tasks.
    Each agent's response lands in ResearchFanIn.
    """

    def __init__(self, id: str, researcher_id: str, host_ids: list[str]):
        super().__init__(id=id)
        self._researcher_id = researcher_id
        self._host_ids = host_ids

    @handler
    async def start(self, request: AgentExecutorRequest, ctx: WorkflowContext) -> None:
        _state.brief = request.messages[-1].contents[-1] if request.messages else ""
        _state.episode_dir = make_episode_dir(_state.brief)
        _state.research_results = []
        _state.research_needed = 1 + len(self._host_ids)  # researcher + all hosts

        research_prompt = AgentExecutorRequest(
            messages=[Message(
                role="user",
                contents=[
                    f"Episode brief:\n\n{_state.brief}\n\n"
                    "Research this topic for the episode."
                ],
            )],
            should_respond=True,
        )

        # Fan out — send to researcher and all hosts simultaneously
        await asyncio.gather(
            ctx.send_message(research_prompt, target_id=self._researcher_id),
            *(ctx.send_message(research_prompt, target_id=hid) for hid in self._host_ids),
        )


class ResearchFanIn(Executor):
    """Collects all parallel research responses.

    Counts down from research_needed. When all agents have responded,
    sends the combined research to the Fact Checker.
    """

    def __init__(self, id: str, fact_checker_id: str):
        super().__init__(id=id)
        self._fact_checker_id = fact_checker_id

    @handler
    async def collect(self, response: AgentExecutorResponse, ctx: WorkflowContext) -> None:
        _state.research_results.append(response.agent_response.text)

        if len(_state.research_results) < _state.research_needed:
            # Still waiting for more research agents to finish
            return

        # All research done — send combined results to fact-checker
        combined = "\n\n---\n\n".join(_state.research_results)
        await ctx.send_message(
            AgentExecutorRequest(
                messages=[Message(
                    role="user",
                    contents=[
                        f"Episode brief:\n\n{_state.brief}\n\n"
                        f"Combined research from all agents:\n\n{combined}\n\n"
                        "Please fact-check this research."
                    ],
                )],
                should_respond=True,
            ),
            target_id=self._fact_checker_id,
        )


# ── Phase 2: Scripting loop ───────────────────────────────────────────────────

class ScriptWriterDispatch(Executor):
    """Routes the Script Writer's draft to the Editor and all Host agents for review.

    This is a parallel fan-out within the scripting loop.
    """

    def __init__(self, id: str, editor_id: str, host_ids: list[str], script_review_fan_in_id: str):
        super().__init__(id=id)
        self._editor_id = editor_id
        self._host_ids = host_ids
        self._fan_in_id = script_review_fan_in_id

    @handler
    async def dispatch(self, response: AgentExecutorResponse, ctx: WorkflowContext) -> None:
        _state.script = response.agent_response.text
        _state.script_cycle += 1

        review_prompt = AgentExecutorRequest(
            messages=[Message(
                role="user",
                contents=[
                    f"Episode brief:\n\n{_state.brief}\n\n"
                    f"Script draft (cycle {_state.script_cycle}):\n\n{_state.script}\n\n"
                    "Review this script."
                ],
            )],
            should_respond=True,
        )

        # Parallel review: Editor + all Hosts
        await asyncio.gather(
            ctx.send_message(review_prompt, target_id=self._editor_id),
            *(ctx.send_message(review_prompt, target_id=hid) for hid in self._host_ids),
        )


class ScriptReviewFanIn(Executor):
    """Collects parallel script reviews, then decides: loop back or advance.

    If the Editor approves and we're within cycle limit → send to Producer.
    If the Editor requests revision → send back to Script Writer.
    """

    def __init__(self, id: str, script_writer_id: str, producer_id: str):
        super().__init__(id=id)
        self._script_writer_id = script_writer_id
        self._producer_id = producer_id
        self._pending_reviews: list[str] = []
        self._reviews_needed: int = 0

    @handler
    async def collect(self, response: AgentExecutorResponse, ctx: WorkflowContext) -> None:
        self._pending_reviews.append(response.agent_response.text)
        reviewers_count = 1 + len([h for h in host_agents])  # editor + all hosts

        if len(self._pending_reviews) < reviewers_count:
            return  # still collecting

        reviews = self._pending_reviews[:]
        self._pending_reviews = []

        # Editor's review is first (it sent first in the gather)
        editor_review = reviews[0]
        host_reviews  = reviews[1:]
        combined_feedback = "\n\n---\n\n".join(reviews)

        if editor_approved(editor_review) or _state.script_cycle >= _state.MAX_SCRIPT_CYCLES:
            # Move to Producer review
            await ctx.send_message(
                AgentExecutorRequest(
                    messages=[Message(
                        role="user",
                        contents=[
                            f"Episode brief:\n\n{_state.brief}\n\n"
                            f"Approved script:\n\n{_state.script}\n\n"
                            "Review this script against the episode brief."
                        ],
                    )],
                    should_respond=True,
                ),
                target_id=self._producer_id,
            )
        else:
            # Send back to Script Writer with all feedback
            await ctx.send_message(
                AgentExecutorRequest(
                    messages=[Message(
                        role="user",
                        contents=[
                            f"Revise the script based on this feedback "
                            f"(cycle {_state.script_cycle}/{_state.MAX_SCRIPT_CYCLES}):\n\n"
                            f"{combined_feedback}\n\n"
                            f"Current script:\n\n{_state.script}"
                        ],
                    )],
                    should_respond=True,
                ),
                target_id=self._script_writer_id,
            )


# ── Phase 3: Producer review loop ────────────────────────────────────────────

class ProducerReviewExecutor(Executor):
    """Producer checks the script against the episode brief.

    If approved or at cycle limit → HITL. Else → Script Writer for revision.
    """

    def __init__(self, id: str, script_writer_id: str, hitl_id: str):
        super().__init__(id=id)
        self._script_writer_id = script_writer_id
        self._hitl_id = hitl_id

    @handler
    async def review(self, response: AgentExecutorResponse, ctx: WorkflowContext) -> None:
        _state.producer_cycle += 1
        producer_text = response.agent_response.text

        if producer_approved(producer_text) or _state.producer_cycle >= _state.MAX_PRODUCER_CYCLES:
            # Advance to human review
            await ctx.send_message(
                ScriptReviewRequest(script=_state.script, round=0),
                target_id=self._hitl_id,
            )
        else:
            await ctx.send_message(
                AgentExecutorRequest(
                    messages=[Message(
                        role="user",
                        contents=[
                            f"Revise the script per Producer feedback "
                            f"(round {_state.producer_cycle}/{_state.MAX_PRODUCER_CYCLES}):\n\n"
                            f"{producer_text}\n\n"
                            f"Current script:\n\n{_state.script}"
                        ],
                    )],
                    should_respond=True,
                ),
                target_id=self._script_writer_id,
            )


# ── HITL: Human script review ─────────────────────────────────────────────────

class ScriptHITLExecutor(Executor):
    """Presents the script to the user for approval or feedback.

    On ACCEPT → write source-script.txt → trigger content pipeline.
    On feedback (max 3 rounds) → Producer interprets → Script Writer revises.
    """

    def __init__(self, id: str, producer_id: str, content_pipeline_id: str):
        super().__init__(id=id)
        self._producer_id = producer_id
        self._content_pipeline_id = content_pipeline_id

    @handler
    async def present(self, request: ScriptReviewRequest, ctx: WorkflowContext) -> None:
        _state.hitl_rounds = request.round
        await ctx.request_info(request_data=request, response_type=str)

    @response_handler
    async def handle(
        self,
        original_request: ScriptReviewRequest,
        response: str,
        ctx: WorkflowContext,
    ) -> None:
        if response.strip().upper() == "ACCEPT" or _state.hitl_rounds >= _state.MAX_HITL_ROUNDS:
            await ctx.send_message(
                AgentExecutorRequest(
                    messages=[Message(role="user", contents=["Write the source script."])],
                    should_respond=False,
                ),
                target_id=self._content_pipeline_id,
            )
        else:
            _state.hitl_rounds += 1
            # Producer interprets the feedback and directs the Script Writer
            await ctx.send_message(
                AgentExecutorRequest(
                    messages=[Message(
                        role="user",
                        contents=[
                            f"The user has reviewed the script and provided feedback "
                            f"(round {_state.hitl_rounds}/{_state.MAX_HITL_ROUNDS}):\n\n"
                            f"{response}\n\n"
                            f"Current script:\n\n{_state.script}\n\n"
                            "Interpret this feedback as a producer and direct the Script Writer "
                            "on what to change. Be specific."
                        ],
                    )],
                    should_respond=True,
                ),
                target_id=self._producer_id,
            )


class ProducerFeedbackRelay(Executor):
    """Relays Producer's interpretation of HITL feedback to the Script Writer,
    then sends the revised script back to HITL for another round."""

    def __init__(self, id: str, script_writer_id: str, hitl_id: str):
        super().__init__(id=id)
        self._script_writer_id = script_writer_id
        self._hitl_id = hitl_id

    @handler
    async def relay(self, response: AgentExecutorResponse, ctx: WorkflowContext) -> None:
        # Producer has interpreted user feedback; send to Script Writer
        await ctx.send_message(
            AgentExecutorRequest(
                messages=[Message(
                    role="user",
                    contents=[
                        f"Producer direction:\n\n{response.agent_response.text}\n\n"
                        f"Current script:\n\n{_state.script}\n\n"
                        "Please revise the script."
                    ],
                )],
                should_respond=True,
            ),
            target_id=self._script_writer_id,
        )

    @handler
    async def route_revision(self, revised: AgentExecutorResponse, ctx: WorkflowContext) -> None:
        # Script Writer has revised; go back to HITL
        _state.script = revised.agent_response.text
        await ctx.send_message(
            ScriptReviewRequest(script=_state.script, round=_state.hitl_rounds),
            target_id=self._hitl_id,
        )


# ── Phase 4: Content pipeline (parallel fan-out) ──────────────────────────────

class ContentPipelineFanOut(Executor):
    """Writes source-script.txt, then fans out to Show Notes, Metadata, and Promo agents."""

    def __init__(self, id: str, show_notes_id: str, metadata_id: str, promo_id: str, save_id: str):
        super().__init__(id=id)
        self._show_notes_id = show_notes_id
        self._metadata_id   = metadata_id
        self._promo_id      = promo_id
        self._save_id       = save_id

    @handler
    async def start(self, request: AgentExecutorRequest, ctx: WorkflowContext) -> None:
        # Write the approved source script to disk
        script_path = _state.episode_dir / "workflow-output" / "source-script.txt"
        script_path.write_text(_state.script)
        await ctx.yield_output(f"Source script saved: {script_path.relative_to(WORKSPACE)}")

        # Reset content accumulator
        _state.content_results = {}

        content_prompt = AgentExecutorRequest(
            messages=[Message(
                role="user",
                contents=[
                    f"Episode brief:\n\n{_state.brief}\n\n"
                    f"Approved script:\n\n{_state.script}\n\n"
                    "Process this episode."
                ],
            )],
            should_respond=True,
        )

        # Fan out to all three content agents simultaneously
        await asyncio.gather(
            ctx.send_message(content_prompt, target_id=self._show_notes_id),
            ctx.send_message(content_prompt, target_id=self._metadata_id),
            ctx.send_message(content_prompt, target_id=self._promo_id),
        )


class ContentPipelineFanIn(Executor):
    """Collects Show Notes, Metadata, and Promo outputs, then writes episode-summary.md."""

    LABELS = {
        "show_notes": "## Show Notes",
        "metadata":   "## Metadata",
        "promo":      "## Promotional Assets",
    }

    def __init__(self, id: str, key: str, save_id: str):
        super().__init__(id=id)
        self._key     = key  # "show_notes" | "metadata" | "promo"
        self._save_id = save_id

    @handler
    async def collect(self, response: AgentExecutorResponse, ctx: WorkflowContext) -> None:
        _state.content_results[self._key] = response.agent_response.text

        if len(_state.content_results) < _state.content_needed:
            return  # still waiting

        # All content is in — write episode-summary.md
        await ctx.send_message(
            AgentExecutorRequest(
                messages=[Message(role="user", contents=["Save the episode summary."])],
                should_respond=False,
            ),
            target_id=self._save_id,
        )


class SaveExecutor(Executor):
    """Writes episode-summary.md and updates show_context.md episode history."""

    @handler
    async def save(self, request: AgentExecutorRequest, ctx: WorkflowContext) -> None:
        summary_parts = [f"# Episode Summary\n\n**Brief:** {_state.brief}\n"]
        for key, label in ContentPipelineFanIn.LABELS.items():
            content = _state.content_results.get(key, "_(not generated)_")
            summary_parts.append(f"{label}\n\n{content}")

        summary = "\n\n---\n\n".join(summary_parts)
        summary_path = _state.episode_dir / "workflow-output" / "episode-summary.md"
        summary_path.write_text(summary)

        append_episode_history(_state.brief, _state.script)

        await ctx.yield_output(
            f"Episode complete!\n\n"
            f"  Source script: {(_state.episode_dir / 'workflow-output' / 'source-script.txt').relative_to(WORKSPACE)}\n"
            f"  Summary:       {summary_path.relative_to(WORKSPACE)}\n\n"
            f"Next: run the audio workflow (Section 4) to generate audio from the source script."
        )


# ── Build the workflow ────────────────────────────────────────────────────────

def build_workflow():
    host_ids = [f"host_{name}" for name, _ in host_agents]

    # Executor instances
    research_fan_out  = ResearchFanOut("research_fan_out", "researcher", host_ids)
    research_fan_in   = ResearchFanIn("research_fan_in", "fact_checker")

    researcher_exec   = AgentExecutor(agent=researcher_agent,   id="researcher")
    fact_checker_exec = AgentExecutor(agent=fact_checker_agent, id="fact_checker")

    host_execs = [
        AgentExecutor(agent=agent, id=f"host_{name}")
        for name, agent in host_agents
    ]

    script_writer_exec  = AgentExecutor(agent=script_writer_agent, id="script_writer")
    editor_exec         = AgentExecutor(agent=editor_agent,        id="editor")
    producer_exec       = AgentExecutor(agent=producer_agent,      id="producer")
    show_notes_exec     = AgentExecutor(agent=show_notes_agent,    id="show_notes")
    metadata_exec       = AgentExecutor(agent=metadata_agent,      id="metadata")
    promo_exec          = AgentExecutor(agent=promo_agent,         id="promo")

    sw_dispatch   = ScriptWriterDispatch("sw_dispatch", "editor", host_ids, "script_review_fan_in")
    sr_fan_in     = ScriptReviewFanIn("script_review_fan_in", "script_writer", "producer")
    producer_rev  = ProducerReviewExecutor("producer_review", "script_writer", "script_hitl")
    script_hitl   = ScriptHITLExecutor("script_hitl", "producer_fb_relay", "content_fan_out")
    producer_fb   = ProducerFeedbackRelay("producer_fb_relay", "script_writer_hitl", "script_hitl")
    sw_hitl_exec  = AgentExecutor(agent=script_writer_agent, id="script_writer_hitl")

    sn_fan_in  = ContentPipelineFanIn("sn_fan_in",   "show_notes", "save")
    md_fan_in  = ContentPipelineFanIn("md_fan_in",   "metadata",   "save")
    pr_fan_in  = ContentPipelineFanIn("pr_fan_in",   "promo",      "save")

    content_fan_out = ContentPipelineFanOut(
        "content_fan_out", "show_notes", "metadata", "promo", "save"
    )
    save_exec = SaveExecutor("save")

    builder = WorkflowBuilder(start_executor=research_fan_out)

    # Phase 1: research fan-out
    builder.add_edge(research_fan_out, researcher_exec)
    for host_exec in host_execs:
        builder.add_edge(research_fan_out, host_exec)
        builder.add_edge(host_exec,        research_fan_in)
    builder.add_edge(researcher_exec,  research_fan_in)
    builder.add_edge(research_fan_in,  fact_checker_exec)

    # Phase 2: scripting loop
    builder.add_edge(fact_checker_exec, script_writer_exec)
    builder.add_edge(script_writer_exec, sw_dispatch)
    builder.add_edge(sw_dispatch,   editor_exec)
    for host_exec in host_execs:
        builder.add_edge(sw_dispatch,   host_exec)
        builder.add_edge(host_exec,     sr_fan_in)
    builder.add_edge(editor_exec,       sr_fan_in)
    builder.add_edge(sr_fan_in,         script_writer_exec)  # revise loop
    builder.add_edge(sr_fan_in,         producer_exec)        # approved path

    # Phase 3: producer review loop
    builder.add_edge(producer_exec,     producer_rev)
    builder.add_edge(producer_rev,      script_writer_exec)   # revise
    builder.add_edge(producer_rev,      script_hitl)          # approved

    # HITL
    builder.add_edge(script_hitl,       producer_fb)
    builder.add_edge(producer_fb,       sw_hitl_exec)
    builder.add_edge(sw_hitl_exec,      script_hitl)          # back to HITL
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
    import logging
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger = logging.getLogger(__name__)
    logger.info("Episode Production Workflow")
    logger.info("DevUI: http://localhost:8090")
    logger.info("Enter an episode brief to start the pipeline.")

    from agent_framework_devui import serve
    serve(entities=[workflow], port=8090, auto_open=True, instrumentation_enabled=True)


if __name__ == "__main__":
    main()
