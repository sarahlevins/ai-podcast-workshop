"""HITL: Human-in-the-loop script review executors."""

from agent_framework import (
    AgentExecutorRequest,
    AgentExecutorResponse,
    Executor,
    Message,
    WorkflowContext,
    handler,
    response_handler,
)

from .state import (
    ScriptReviewRequest,
    _log_artifact,
    _run_logger,
    _state,
)


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
        _run_logger.info("HITL round %d — waiting for human feedback", _state.hitl_rounds)
        _log_artifact(
            f"hitl_round_{_state.hitl_rounds:02d}_presented.md",
            f"# HITL Round {_state.hitl_rounds} — Script Presented\n\n{request.script}",
        )
        await ctx.request_info(request_data=request, response_type=str)

    @response_handler
    async def handle(
        self,
        original_request: ScriptReviewRequest,
        response: str,
        ctx: WorkflowContext[AgentExecutorRequest],
    ) -> None:
        _run_logger.info("HITL round %d — human responded: %r", _state.hitl_rounds, response[:80])
        _log_artifact(
            f"hitl_round_{_state.hitl_rounds:02d}_feedback.txt",
            response,
        )
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


class ScriptRevisionRelay(Executor):
    """Sends the Script Writer's revised script back to HITL for another round."""

    def __init__(self, id: str, hitl_id: str):
        super().__init__(id=id)
        self._hitl_id = hitl_id

    @handler
    async def route_revision(self, revised: AgentExecutorResponse, ctx: WorkflowContext[ScriptReviewRequest]) -> None:
        # Script Writer has revised; go back to HITL
        _state.script = revised.agent_response.text
        await ctx.send_message(
            ScriptReviewRequest(script=_state.script, round=_state.hitl_rounds),
            target_id=self._hitl_id,
        )
