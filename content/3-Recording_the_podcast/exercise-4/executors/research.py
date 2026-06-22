"""Phase 1: Research fan-out / fan-in executors."""

import asyncio

from agent_framework import (
    AgentExecutorRequest,
    AgentExecutorResponse,
    Executor,
    Message,
    WorkflowContext,
    handler,
)

from .state import (
    EpisodeBriefInput,
    _log_artifact,
    _run_logger,
    _start_run_logging,
    _state,
    make_episode_dir,
)


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
    async def start(self, request: EpisodeBriefInput, ctx: WorkflowContext[AgentExecutorRequest]) -> None:
        _state.brief = request.brief or _state.cli_brief
        _state.episode_dir = make_episode_dir(_state.brief)

        # Reset all per-run counters so a second dev-UI run starts clean
        _state.research_results = []
        _state.research_needed = 1 + len(self._host_ids)  # researcher + all hosts
        _state.script = ""
        _state.script_cycle = 0
        _state.producer_cycle = 0
        _state.hitl_rounds = 0
        _state.content_results = {}

        _start_run_logging()

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
    async def collect(self, response: AgentExecutorResponse, ctx: WorkflowContext[AgentExecutorRequest]) -> None:
        _state.research_results.append(response.agent_response.text)

        if len(_state.research_results) < _state.research_needed:
            # Still waiting for more research agents to finish
            return

        # All research done — log and send combined results to fact-checker
        combined = "\n\n---\n\n".join(_state.research_results)
        _log_artifact("research.md", f"# Combined Research\n\n{combined}")
        _run_logger.info("research complete (%d sources)", len(_state.research_results))
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
