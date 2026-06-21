"""Phase 4: Content pipeline executors."""

import asyncio
import json
from datetime import datetime
from typing import Never

from agent_framework import (
    AgentExecutorRequest,
    AgentExecutorResponse,
    Executor,
    Message,
    WorkflowContext,
    handler,
)

from .state import (
    WORKSPACE,
    _log_artifact,
    _run_logger,
    _state,
    append_episode_history,
)


class ContentPipelineFanOut(Executor):
    """Writes source-script.txt, then fans out to Show Notes, Metadata, and Promo agents."""

    def __init__(self, id: str, show_notes_id: str, metadata_id: str, promo_id: str, save_id: str):
        super().__init__(id=id)
        self._show_notes_id = show_notes_id
        self._metadata_id   = metadata_id
        self._promo_id      = promo_id
        self._save_id       = save_id

    @handler
    async def start(self, request: AgentExecutorRequest, ctx: WorkflowContext[AgentExecutorRequest, str]) -> None:
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
    async def collect(self, response: AgentExecutorResponse, ctx: WorkflowContext[AgentExecutorRequest]) -> None:
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
    async def save(self, request: AgentExecutorRequest, ctx: WorkflowContext[Never, str]) -> None:
        summary_parts = [f"# Episode Summary\n\n**Brief:** {_state.brief}\n"]
        for key, label in ContentPipelineFanIn.LABELS.items():
            content = _state.content_results.get(key, "_(not generated)_")
            summary_parts.append(f"{label}\n\n{content}")

        summary = "\n\n---\n\n".join(summary_parts)
        summary_path = _state.episode_dir / "workflow-output" / "episode-summary.md"
        summary_path.write_text(summary)

        append_episode_history(_state.brief, _state.script)

        _log_artifact("scripts/final.md", f"# Final Script\n\n{_state.script}")
        manifest_path = _run_logger.run_log_dir / "manifest.json"
        if manifest_path.exists():
            m = json.loads(manifest_path.read_text())
            m["completed_at"] = datetime.now().isoformat()
            m["episode_dir"] = str(_state.episode_dir.relative_to(WORKSPACE))
            m["script_cycles"] = _state.script_cycle
            m["hitl_rounds"] = _state.hitl_rounds
            manifest_path.write_text(json.dumps(m, indent=2))
        _run_logger.info("=== run %s complete ===", _run_logger.run_id)

        await ctx.yield_output(
            f"Episode complete!\n\n"
            f"  Source script: {(_state.episode_dir / 'workflow-output' / 'source-script.txt').relative_to(WORKSPACE)}\n"
            f"  Summary:       {summary_path.relative_to(WORKSPACE)}\n\n"
            f"Next: run the audio workflow (Section 4) to generate audio from the source script."
        )
