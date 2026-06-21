"""Audio Workflow — Section 4.

Takes the source-script.txt produced by Section 3 and walks through:
  1. Backend selection  — user picks: vibevoice-1.5b / vibevoice-7b / mai2
  2. Script Formatter   — converts source script to the chosen backend's format
  3. Audio Engineer     — generates segments (mai2) or outputs notebook instructions (vibevoice)
  4. HITL checkpoint    — waits for user to place vibevoice segments (skipped for mai2)
  5. Post-Production    — generates assembly plan JSON from segment files

Run:
    python content/4-Executing-the-workflow/audio-workflow/workflow.py [<episode-slug>]

If no slug is given the workflow picks the most recent episode directory.

Output paths (within the episode directory):
  artifacts/vibevoice/script.txt        (vibevoice mode)
  artifacts/azure-ssml/script.xml       (azure-ssml mode — not used here)
  artifacts/mai2/script.xml             (mai2 mode)
  audio/segments/segment_NNN.mp3        (mai2 generated automatically)
  audio/podcast-assembly-plan.json      (post-production deliverable)
"""

import json
import re
import sys
from dataclasses import dataclass
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

from agents.script_formatter import create_script_formatter  # noqa: E402
from agents.audio_engineer   import create_audio_engineer    # noqa: E402
from agents.post_production  import create_post_production   # noqa: E402

# ── Show context & episode selection ─────────────────────────────────────────

SHOW_CONTEXT_PATH = WORKSPACE / "output" / "show_context.md"
EPISODES_DIR      = WORKSPACE / "output" / "episodes"

if not SHOW_CONTEXT_PATH.exists():
    raise FileNotFoundError(
        f"{SHOW_CONTEXT_PATH} not found.\n"
        "Run the Show Setup Workflow first:\n"
        "  python content/2-Developing_the_concept/exercise/chat.py"
    )

SHOW_CONTEXT = SHOW_CONTEXT_PATH.read_text()


def _find_episode_dir(slug: str | None) -> Path:
    if slug:
        candidates = list(EPISODES_DIR.glob(f"*{slug}*"))
        if not candidates:
            raise FileNotFoundError(f"No episode directory matching '{slug}' in {EPISODES_DIR}")
        return sorted(candidates)[-1]

    dirs = sorted(EPISODES_DIR.iterdir())
    if not dirs:
        raise FileNotFoundError(
            f"No episode directories in {EPISODES_DIR}.\n"
            "Run the Episode Production Workflow first (Section 3)."
        )
    return dirs[-1]


_episode_dir: Path | None = None  # set during BackendSelectExecutor


# ── Backend + pipeline state ──────────────────────────────────────────────────

VALID_BACKENDS = {"vibevoice-1.5b", "vibevoice-7b", "mai2"}


@dataclass
class PipelineState:
    episode_dir: Path = None
    backend: str = ""
    source_script: str = ""
    formatted_script: str = ""
    artifact_path: Path = None


_state = PipelineState()


# ── Human-in-the-loop request types ──────────────────────────────────────────

@dataclass
class BackendSelectRequest:
    source_script_preview: str
    prompt: str = (
        "Which TTS backend would you like to use?\n"
        "  • vibevoice-1.5b  — fast, good quality, requires GPU notebook\n"
        "  • vibevoice-7b    — best quality, requires A100 GPU notebook\n"
        "  • mai2            — Azure MAI Voice 2, runs locally if keys are set\n\n"
        "Enter backend name:"
    )


@dataclass
class VibeVoiceReadyRequest:
    instructions: str
    prompt: str = "When your audio segments are in audio/segments/, type 'ready' to continue:"


# ── Executors ─────────────────────────────────────────────────────────────────

class BackendSelectExecutor(Executor):
    """Loads the source script and prompts the user to choose a TTS backend."""

    def __init__(self, id: str, formatter_id: str, slug: str | None = None):
        super().__init__(id=id)
        self._formatter_id = formatter_id
        self._slug = slug

    @handler
    async def start(self, request: AgentExecutorRequest, ctx: WorkflowContext) -> None:
        global _episode_dir
        _episode_dir = _find_episode_dir(self._slug)
        _state.episode_dir = _episode_dir

        source_path = _episode_dir / "workflow-output" / "source-script.txt"
        if not source_path.exists():
            await ctx.yield_output(
                f"No source-script.txt found in {source_path.parent}.\n"
                "Run the Episode Production Workflow (Section 3) first."
            )
            return

        _state.source_script = source_path.read_text()
        await ctx.request_info(
            request_data=BackendSelectRequest(
                source_script_preview=_state.source_script[:500] + "…"
            ),
            response_type=str,
        )

    @response_handler
    async def handle_backend(
        self,
        original_request: BackendSelectRequest,
        response: str,
        ctx: WorkflowContext,
    ) -> None:
        backend = response.strip().lower()
        if backend not in VALID_BACKENDS:
            await ctx.yield_output(
                f"Unknown backend '{backend}'. Choose one of: {', '.join(sorted(VALID_BACKENDS))}"
            )
            await ctx.request_info(request_data=original_request, response_type=str)
            return

        _state.backend = backend
        await ctx.yield_output(f"Backend selected: {backend}")

        # Build the formatting prompt
        await ctx.send_message(
            AgentExecutorRequest(
                messages=[Message(
                    role="user",
                    contents=[
                        f"Backend: {backend}\n\n"
                        f"Source script:\n\n{_state.source_script}\n\n"
                        f"Format this script for the {backend} backend. "
                        "Use the voice IDs from Show Context for host-to-voice mapping."
                    ],
                )],
                should_respond=True,
            ),
            target_id=self._formatter_id,
        )


class FormattedScriptSaveExecutor(Executor):
    """Receives the formatted script, saves it to the appropriate artifact path,
    then dispatches to the Audio Engineer."""

    def __init__(self, id: str, audio_engineer_id: str):
        super().__init__(id=id)
        self._audio_engineer_id = audio_engineer_id

    @handler
    async def save(self, response: AgentExecutorResponse, ctx: WorkflowContext) -> None:
        _state.formatted_script = response.agent_response.text

        backend = _state.backend
        ep_dir  = _state.episode_dir

        if backend in ("vibevoice-1.5b", "vibevoice-7b"):
            artifact_path = ep_dir / "artifacts" / "vibevoice" / "script.txt"
        elif backend == "mai2":
            artifact_path = ep_dir / "artifacts" / "mai2" / "script.xml"
        else:
            artifact_path = ep_dir / "artifacts" / f"{backend}-script.txt"

        artifact_path.parent.mkdir(parents=True, exist_ok=True)
        artifact_path.write_text(_state.formatted_script)
        _state.artifact_path = artifact_path

        await ctx.yield_output(
            f"Formatted script saved: {artifact_path.relative_to(WORKSPACE)}"
        )

        await ctx.send_message(
            AgentExecutorRequest(
                messages=[Message(
                    role="user",
                    contents=[
                        f"Backend: {backend}\n"
                        f"Formatted script path: {artifact_path.relative_to(WORKSPACE)}\n"
                        f"Episode segments directory: "
                        f"{(ep_dir / 'audio' / 'segments').relative_to(WORKSPACE)}\n\n"
                        f"Formatted script:\n\n{_state.formatted_script}\n\n"
                        "Process this script for audio generation."
                    ],
                )],
                should_respond=True,
            ),
            target_id=self._audio_engineer_id,
        )


class AudioEngineerDispatch(Executor):
    """Receives the Audio Engineer's response.

    For mai2: engineer has already called the API. Move to Post-Production.
    For vibevoice: engineer has output instructions. Show them to the user and wait.
    """

    def __init__(self, id: str, hitl_id: str, post_production_id: str):
        super().__init__(id=id)
        self._hitl_id = hitl_id
        self._post_production_id = post_production_id

    @handler
    async def dispatch(self, response: AgentExecutorResponse, ctx: WorkflowContext) -> None:
        engineer_output = response.agent_response.text

        if _state.backend == "mai2":
            # Segments should already be written by the engineer; go to post-production
            segments_dir = _state.episode_dir / "audio" / "segments"
            await ctx.send_message(
                AgentExecutorRequest(
                    messages=[Message(
                        role="user",
                        contents=[
                            f"Segments directory: {segments_dir.relative_to(WORKSPACE)}\n"
                            f"Segment files: {sorted(str(p.name) for p in segments_dir.glob('*.mp3'))}\n"
                            f"Episode directory: {_state.episode_dir.relative_to(WORKSPACE)}\n\n"
                            "Generate the assembly plan JSON."
                        ],
                    )],
                    should_respond=True,
                ),
                target_id=self._post_production_id,
            )
        else:
            # vibevoice — show instructions and wait for user
            await ctx.request_info(
                request_data=VibeVoiceReadyRequest(instructions=engineer_output),
                response_type=str,
            )

    @response_handler
    async def handle_ready(
        self,
        original_request: VibeVoiceReadyRequest,
        response: str,
        ctx: WorkflowContext,
    ) -> None:
        if response.strip().lower() != "ready":
            await ctx.yield_output("Waiting for segments. Type 'ready' when done.")
            await ctx.request_info(request_data=original_request, response_type=str)
            return

        segments_dir = _state.episode_dir / "audio" / "segments"
        segment_files = sorted(segments_dir.glob("*.mp3"))

        if not segment_files:
            await ctx.yield_output(
                f"No .mp3 files found in {segments_dir.relative_to(WORKSPACE)}.\n"
                "Place the downloaded segment files there and type 'ready' again."
            )
            await ctx.request_info(request_data=original_request, response_type=str)
            return

        await ctx.send_message(
            AgentExecutorRequest(
                messages=[Message(
                    role="user",
                    contents=[
                        f"Segments directory: {segments_dir.relative_to(WORKSPACE)}\n"
                        f"Segment files: {[p.name for p in segment_files]}\n"
                        f"Episode directory: {_state.episode_dir.relative_to(WORKSPACE)}\n\n"
                        "Generate the assembly plan JSON."
                    ],
                )],
                should_respond=True,
            ),
            target_id=self._post_production_id,
        )


class AssemblyPlanSaveExecutor(Executor):
    """Saves the Post-Production agent's assembly plan JSON to disk."""

    @handler
    async def save(self, response: AgentExecutorResponse, ctx: WorkflowContext) -> None:
        plan_text = response.agent_response.text

        # Extract JSON if wrapped in a code fence
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", plan_text, re.DOTALL)
        plan_json = match.group(1) if match else plan_text.strip()

        # Validate JSON before writing
        try:
            json.loads(plan_json)
        except json.JSONDecodeError as e:
            await ctx.yield_output(f"Assembly plan JSON parse error: {e}\n\nRaw output:\n{plan_text}")
            return

        plan_path = _state.episode_dir / "audio" / "podcast-assembly-plan.json"
        plan_path.write_text(plan_json)

        await ctx.yield_output(
            f"Assembly plan saved: {plan_path.relative_to(WORKSPACE)}\n\n"
            f"Section 4 complete.\n"
            f"  Formatted script: {_state.artifact_path.relative_to(WORKSPACE)}\n"
            f"  Assembly plan:    {plan_path.relative_to(WORKSPACE)}\n\n"
            "To mix the audio, implement the Mix Executor using the assembly plan JSON.\n"
            "See the 'Dependency note' in revision-plan.md for mixing library options."
        )


# ── Build the workflow ────────────────────────────────────────────────────────

def build_workflow(slug: str | None = None):
    formatter_agent      = create_script_formatter(SHOW_CONTEXT)
    audio_engineer_agent = create_audio_engineer(SHOW_CONTEXT)
    post_production_agent = create_post_production(SHOW_CONTEXT)

    formatter_exec    = AgentExecutor(agent=formatter_agent,       id="formatter")
    audio_eng_exec    = AgentExecutor(agent=audio_engineer_agent,  id="audio_engineer")
    post_prod_exec    = AgentExecutor(agent=post_production_agent, id="post_production")

    backend_select    = BackendSelectExecutor("backend_select", "fmt_save", slug=slug)
    fmt_save          = FormattedScriptSaveExecutor("fmt_save", "audio_eng_dispatch")
    audio_eng_disp    = AudioEngineerDispatch("audio_eng_dispatch", "audio_eng_dispatch", "plan_save")
    plan_save         = AssemblyPlanSaveExecutor("plan_save")

    return (
        WorkflowBuilder(start_executor=backend_select)
        # Backend → formatter
        .add_edge(backend_select,  formatter_exec)
        .add_edge(formatter_exec,  fmt_save)
        # Formatted script → audio engineer
        .add_edge(fmt_save,        audio_eng_exec)
        .add_edge(audio_eng_exec,  audio_eng_disp)
        # Audio done → post-production
        .add_edge(audio_eng_disp,  post_prod_exec)
        # Post-production → save assembly plan
        .add_edge(post_prod_exec,  plan_save)
        .build()
    )


def main():
    import logging
    import sys as _sys

    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger = logging.getLogger(__name__)

    slug = _sys.argv[1] if len(_sys.argv) > 1 else None
    global workflow
    workflow = build_workflow(slug)

    logger.info("Audio Workflow — Section 4")
    logger.info("DevUI: http://localhost:8090")

    from agent_framework_devui import serve
    serve(entities=[workflow], port=8090, auto_open=True, instrumentation_enabled=True)


# Module-level workflow (no slug — picks most recent episode)
workflow = build_workflow()

if __name__ == "__main__":
    main()
