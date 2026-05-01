"""Artifact builder workflow with host confirmation loop."""

from dataclasses import dataclass
from pathlib import Path
from datetime import datetime

from agent_framework import (
    WorkflowBuilder,
    WorkflowContext,
    Executor,
    AgentExecutorResponse,
    AgentExecutorRequest,
    Message,
    handler,
    response_handler,
    AgentExecutor,
)
from agent import setup_builder_agent


@dataclass
class HostApprovalRequest:
    """Request for user to approve or reject the proposed hosts."""
    prompt: str
    proposed_hosts: str


class ReviewExecutor(Executor):
    """Executor that requests user approval of the proposed hosts."""

    def __init__(self, id: str, builder_agent_id: str):
        super().__init__(id=id)
        self._builder_agent_id = builder_agent_id

    @handler
    async def review_hosts(self, response: AgentExecutorResponse, ctx: WorkflowContext) -> None:
        """Present the agent's host proposal for user approval."""
        proposal_text = response.agent_response.text

        await ctx.request_info(
            request_data=HostApprovalRequest(
                prompt="Are you happy with these hosts? Type 'yes' to accept, or describe what you'd like to change.",
                proposed_hosts=proposal_text,
            ),
            response_type=str,
        )

    @response_handler
    async def handle_approval(
        self,
        original_request: HostApprovalRequest,
        response: str,
        ctx: WorkflowContext[AgentExecutorRequest],
    ) -> None:
        """Route the user's response."""
        user_input = response.strip()

        if user_input.lower() == "yes":
            # Approved - tell the builder agent to proceed with writing artifacts
            proceed_message = Message(
                role="user",
                contents=["The user approved the hosts. Now proceed to steps 4-6: build the host definitions, produce the artifacts, and report back."],
            )
            await ctx.send_message(
                AgentExecutorRequest(messages=[proceed_message], should_respond=True),
                target_id=self._builder_agent_id,
            )
        else:
            # Not approved - send feedback back to the builder agent
            feedback_message = Message(
                role="user",
                contents=[f"The user wants changes to the host selection: {user_input}. Please propose new hosts based on this feedback."],
            )
            await ctx.send_message(
                AgentExecutorRequest(messages=[feedback_message], should_respond=True),
                target_id=self._builder_agent_id,
            )


class SaveExecutor(Executor):
    """Saves the final report once the builder agent finishes writing artifacts."""

    @handler
    async def save_report(self, response: AgentExecutorResponse, ctx: WorkflowContext) -> None:
        report = response.agent_response.text
        await ctx.yield_output(report)


# Setup
builder_agent = setup_builder_agent()

builder_executor = AgentExecutor(agent=builder_agent, id="builder_executor")
review_executor = ReviewExecutor(id="review_executor", builder_agent_id="builder_executor")
save_executor = SaveExecutor(id="save_executor")

workflow = (
    WorkflowBuilder(start_executor=builder_executor)
    .add_edge(builder_executor, review_executor)
    .add_edge(review_executor, builder_executor)   # loop back for changes or to write artifacts
    .add_edge(builder_executor, save_executor)      # final output after writing
    .build()
)
