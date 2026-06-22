"""Phase 3: Producer review loop executors."""

from agent_framework import (
    AgentExecutorRequest,
    AgentExecutorResponse,
    Executor,
    Message,
    WorkflowContext,
    handler,
)

from .state import (
    ScriptReviewRequest,
    _log_artifact,
    _run_logger,
    _state,
    producer_approved,
)


class ProducerReviewExecutor(Executor):
    """Producer checks the script against the episode brief.

    If approved or at cycle limit → HITL. Else → Script Writer for revision.
    """

    def __init__(self, id: str, script_writer_id: str, hitl_id: str):
        super().__init__(id=id)
        self._script_writer_id = script_writer_id
        self._hitl_id = hitl_id

    @handler
    async def review(self, response: AgentExecutorResponse, ctx: WorkflowContext[AgentExecutorRequest | ScriptReviewRequest]) -> None:
        _state.producer_cycle += 1
        producer_text = response.agent_response.text
        _log_artifact(
            f"producer_review_{_state.producer_cycle:02d}.md",
            f"# Producer Review {_state.producer_cycle}\n\n{producer_text}",
        )
        _run_logger.info("producer review %d complete", _state.producer_cycle)

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


class ProducerFeedbackRelay(Executor):
    """Relays Producer's interpretation of HITL feedback to the Script Writer."""

    def __init__(self, id: str, script_writer_id: str):
        super().__init__(id=id)
        self._script_writer_id = script_writer_id

    @handler
    async def relay(self, response: AgentExecutorResponse, ctx: WorkflowContext[AgentExecutorRequest]) -> None:
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
