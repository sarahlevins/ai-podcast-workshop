"""Phase 2: Scripting loop executors."""

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
    _log_artifact,
    _run_logger,
    _state,
    editor_approved,
)


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
    async def dispatch(self, response: AgentExecutorResponse, ctx: WorkflowContext[AgentExecutorRequest]) -> None:
        _state.script = response.agent_response.text
        _state.script_cycle += 1
        _log_artifact(
            f"scripts/draft_{_state.script_cycle:02d}.md",
            f"# Script Draft {_state.script_cycle}\n\n{_state.script}",
        )
        _run_logger.info("script draft %d written (%d chars)", _state.script_cycle, len(_state.script))

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

    def __init__(self, id: str, script_writer_id: str, producer_id: str, host_count: int):
        super().__init__(id=id)
        self._script_writer_id = script_writer_id
        self._producer_id = producer_id
        self._reviewers_count = 1 + host_count  # editor + all hosts
        self._pending_reviews: list[str] = []

    @handler
    async def collect(self, response: AgentExecutorResponse, ctx: WorkflowContext[AgentExecutorRequest]) -> None:
        self._pending_reviews.append(response.agent_response.text)

        if len(self._pending_reviews) < self._reviewers_count:
            return  # still collecting

        reviews = self._pending_reviews[:]
        self._pending_reviews = []

        # Editor's review is first (it sent first in the gather)
        editor_review = reviews[0]
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
