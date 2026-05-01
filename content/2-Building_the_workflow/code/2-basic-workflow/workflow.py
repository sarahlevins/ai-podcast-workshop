"""
Podcast production workflow with human review gates.

Pipeline:
  Producer → Researcher → Script Writer → Editor
                                           ↓
                                    [User reviews script]
                                     ↙ feedback    ↘ approved
                                   Editor         Publisher
                                                     ↓
                                            [User reviews packet]
                                             ↙ feedback  ↘ approved
                                          Publisher      Save to disk
"""
import sys
import logging
from dataclasses import dataclass
from datetime import datetime
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

# ── Paths ─────────────────────────────────────────────────────────────────────

ARTIFACTS_DIR = WORKSPACE / "content/1-Understanding_the_workflow/podcast-agent-artifacts"
OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def _load(role: str) -> str:
    path = ARTIFACTS_DIR / f"{role}.txt"
    if not path.exists():
        raise FileNotFoundError(
            f"Artifact not found: {path}\n"
            "Run the artifact builder in Step 1 first."
        )
    return path.read_text()


# ── Agents ────────────────────────────────────────────────────────────────────

producer_agent   = create_agent(AgentOptions(name="Producer",     instructions=_load("producer")))
researcher_agent = create_agent(AgentOptions(name="Researcher",   instructions=_load("research")))
writer_agent     = create_agent(AgentOptions(name="ScriptWriter", instructions=_load("script-writer")))
editor_agent     = create_agent(AgentOptions(name="Editor",       instructions=_load("editor")))
publisher_agent  = create_agent(AgentOptions(name="Publisher",    instructions=_load("publisher")))


# ── Shared pipeline state ─────────────────────────────────────────────────────
# Simple dict to carry the approved script and packet across executors.

_pipeline: dict[str, str] = {"script": "", "packet": ""}


# ── Human review request types ────────────────────────────────────────────────

@dataclass
class ScriptReviewRequest:
    script: str
    prompt: str = (
        "Happy with the edited script?\n"
        "  • Type 'yes' to send to the publisher.\n"
        "  • Or describe what to change and the editor will revise it."
    )


@dataclass
class PublishReviewRequest:
    packet: str
    prompt: str = (
        "Happy with the publish packet?\n"
        "  • Type 'yes' to save both files to disk.\n"
        "  • Or describe what to change and the publisher will revise it."
    )


# ── Custom executors ──────────────────────────────────────────────────────────

class ScriptReviewExecutor(Executor):
    """Presents the edited script to the user.
    Routes to editor (with feedback) or publisher (on approval)."""

    def __init__(self, id: str, editor_id: str, publisher_id: str):
        super().__init__(id=id)
        self._editor_id = editor_id
        self._publisher_id = publisher_id

    @handler
    async def review(self, response: AgentExecutorResponse, ctx: WorkflowContext) -> None:
        _pipeline["script"] = response.agent_response.text
        await ctx.request_info(
            request_data=ScriptReviewRequest(script=_pipeline["script"]),
            response_type=str,
        )

    @response_handler
    async def handle_review(
        self,
        original_request: ScriptReviewRequest,
        response: str,
        ctx: WorkflowContext[AgentExecutorRequest],
    ) -> None:
        if response.strip().lower() == "yes":
            await ctx.send_message(
                AgentExecutorRequest(
                    messages=[Message(
                        role="user",
                        contents=[
                            f"Here is the approved script:\n\n{_pipeline['script']}\n\n"
                            "Please produce the full publish packet: a compelling episode title, "
                            "show notes (150–200 words), chapter markers with timestamps, and "
                            "social media copy for Twitter/X and LinkedIn."
                        ],
                    )],
                    should_respond=True,
                ),
                target_id=self._publisher_id,
            )
        else:
            await ctx.send_message(
                AgentExecutorRequest(
                    messages=[Message(
                        role="user",
                        contents=[f"Please revise the script. Reviewer feedback: {response}"],
                    )],
                    should_respond=True,
                ),
                target_id=self._editor_id,
            )


class PublishReviewExecutor(Executor):
    """Presents the publish packet to the user.
    Routes to publisher (with feedback) or save executor (on approval)."""

    def __init__(self, id: str, publisher_id: str, save_id: str):
        super().__init__(id=id)
        self._publisher_id = publisher_id
        self._save_id = save_id

    @handler
    async def review(self, response: AgentExecutorResponse, ctx: WorkflowContext) -> None:
        _pipeline["packet"] = response.agent_response.text
        await ctx.request_info(
            request_data=PublishReviewRequest(packet=_pipeline["packet"]),
            response_type=str,
        )

    @response_handler
    async def handle_review(
        self,
        original_request: PublishReviewRequest,
        response: str,
        ctx: WorkflowContext[AgentExecutorRequest],
    ) -> None:
        if response.strip().lower() == "yes":
            await ctx.send_message(
                AgentExecutorRequest(
                    messages=[Message(
                        role="user",
                        contents=["Save the approved script and publish packet."],
                    )],
                    should_respond=False,
                ),
                target_id=self._save_id,
            )
        else:
            await ctx.send_message(
                AgentExecutorRequest(
                    messages=[Message(
                        role="user",
                        contents=[f"Please revise the publish packet. Feedback: {response}"],
                    )],
                    should_respond=True,
                ),
                target_id=self._publisher_id,
            )


def _to_vibevoice(script: str) -> str:
    """Strip section headers, editor's notes, and markdown from a script.

    VibeVoice-TTS expects plain `Speaker: dialogue` lines with no square-bracket
    headers (which conflict with ASR timestamp format) and no markdown formatting.
    """
    import re
    lines = []
    for line in script.splitlines():
        # Stop at any editor's notes block
        if re.match(r"^\[Editor", line, re.IGNORECASE):
            break
        # Drop section header lines — e.g. [Cold Open], [Segment 1: ...]
        # These are full-line bracket markers, not inline references
        if re.match(r"^\[.+\]\s*$", line):
            continue
        # Strip markdown bold/italic asterisks: *word* → word
        line = re.sub(r"\*([^*]+)\*", r"\1", line)
        lines.append(line)
    # Collapse runs of 3+ blank lines to a single blank line
    cleaned = re.sub(r"\n{3,}", "\n\n", "\n".join(lines))
    return cleaned.strip()


class SaveExecutor(Executor):
    """Saves the approved script, VibeVoice-compatible script, and publish packet."""

    @handler
    async def save(self, request: AgentExecutorRequest, ctx: WorkflowContext) -> None:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        script_path   = OUTPUT_DIR / f"script_{timestamp}.txt"
        vibevoice_path = OUTPUT_DIR / f"script_{timestamp}_vibevoice.txt"
        packet_path   = OUTPUT_DIR / f"publisher_notes_{timestamp}.txt"

        script_path.write_text(_pipeline["script"])
        vibevoice_path.write_text(_to_vibevoice(_pipeline["script"]))
        packet_path.write_text(_pipeline["packet"])

        summary = (
            f"Episode saved successfully!\n\n"
            f"  Script (full):      {script_path.name}\n"
            f"  Script (VibeVoice): {vibevoice_path.name}\n"
            f"  Publisher notes:    {packet_path.name}\n"
            f"  Location:           {OUTPUT_DIR}"
        )
        await ctx.yield_output(summary)


# ── Executor instances ────────────────────────────────────────────────────────

producer_exec      = AgentExecutor(agent=producer_agent,   id="producer")
researcher_exec    = AgentExecutor(agent=researcher_agent, id="researcher",   context_mode="last_agent")
writer_exec        = AgentExecutor(agent=writer_agent,     id="script_writer")
editor_exec        = AgentExecutor(agent=editor_agent,     id="editor",       context_mode="last_agent")
script_review_exec = ScriptReviewExecutor(id="script_review", editor_id="editor", publisher_id="publisher")
publisher_exec     = AgentExecutor(agent=publisher_agent,  id="publisher")
publish_review_exec = PublishReviewExecutor(id="publish_review", publisher_id="publisher", save_id="save")
save_exec          = SaveExecutor(id="save")


# ── Workflow graph ────────────────────────────────────────────────────────────

workflow = (
    WorkflowBuilder(start_executor=producer_exec)
    # Linear production pipeline
    .add_edge(producer_exec,    researcher_exec)
    .add_edge(researcher_exec,  writer_exec)
    .add_edge(writer_exec,      editor_exec)
    .add_edge(editor_exec,      script_review_exec)
    # Script review: feedback loops back to editor, approval goes to publisher
    .add_edge(script_review_exec, editor_exec)
    .add_edge(script_review_exec, publisher_exec)
    # Publish review: feedback loops back to publisher, approval goes to save
    .add_edge(publisher_exec,     publish_review_exec)
    .add_edge(publish_review_exec, publisher_exec)
    .add_edge(publish_review_exec, save_exec)
    .build()
)


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger = logging.getLogger(__name__)
    logger.info("Starting Podcast Production Workflow")
    logger.info("DevUI available at: http://localhost:8090")

    from agent_framework_devui import serve
    serve(entities=[workflow], port=8090, auto_open=True, instrumentation_enabled=True)


if __name__ == "__main__":
    main()
