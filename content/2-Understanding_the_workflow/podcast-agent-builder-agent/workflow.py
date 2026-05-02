"""Concept builder workflow.

Flow:
  1. BuilderAgent expands the user's brief into a concept + 2 hosts (JSON).
  2. ReviewExecutor parses the JSON and asks the user to confirm.
  3. On approval, TemplateExecutor programmatically fills the role
     templates with string replacement and writes them to disk.
"""

import json
from dataclasses import dataclass

from agent_framework import (
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

from agent import (
    HOST_FILES,
    HOSTS_DIR,
    OUTPUT_DIR,
    ROLES,
    TEMPLATES_DIR,
    WORKING_DIR,
    ConceptProposal,
    parse_proposal,
    setup_builder_agent,
)


@dataclass
class ConceptApprovalRequest:
    """Request for user to approve or revise the proposed concept."""
    prompt: str
    proposal: ConceptProposal


class ReviewExecutor(Executor):
    """Asks the user to confirm the agent's proposal."""

    def __init__(self, id: str, builder_agent_id: str, template_executor_id: str):
        super().__init__(id=id)
        self._builder_agent_id = builder_agent_id
        self._template_executor_id = template_executor_id

    @handler
    async def review(self, response: AgentExecutorResponse, ctx: WorkflowContext) -> None:
        try:
            proposal = parse_proposal(response.agent_response.text)
        except (json.JSONDecodeError, KeyError) as e:
            await ctx.send_message(
                AgentExecutorRequest(
                    messages=[Message(
                        role="user",
                        contents=[f"Your previous response could not be parsed as the required JSON ({e}). Please respond again with a single ```json fenced block matching the schema."],
                    )],
                    should_respond=True,
                ),
                target_id=self._builder_agent_id,
            )
            return

        await ctx.request_info(
            request_data=ConceptApprovalRequest(
                prompt="Approve this concept? Type 'yes' to write artifacts, or describe changes.",
                proposal=proposal,
            ),
            response_type=str,
        )

    @response_handler
    async def handle_approval(
        self,
        original_request: ConceptApprovalRequest,
        response: str,
        ctx: WorkflowContext,
    ) -> None:
        user_input = response.strip()
        if user_input.lower() == "yes":
            await ctx.send_message(original_request.proposal, target_id=self._template_executor_id)
        else:
            await ctx.send_message(
                AgentExecutorRequest(
                    messages=[Message(
                        role="user",
                        contents=[f"The user wants changes: {user_input}. Revise and respond again in the same JSON format."],
                    )],
                    should_respond=True,
                ),
                target_id=self._builder_agent_id,
            )


class TemplateExecutor(Executor):
    """Fills role templates by string replacement and writes the artifacts."""

    @handler
    async def write_artifacts(self, proposal: ConceptProposal, ctx: WorkflowContext) -> None:
        unknown = [h for h in proposal.hosts if h not in HOST_FILES]
        if unknown:
            await ctx.yield_output(f"Error: agent proposed unknown host(s): {unknown}.")
            return

        host_definitions = "\n\n".join(
            (HOSTS_DIR / HOST_FILES[h]).read_text().rstrip() for h in proposal.hosts
        )

        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        written = []
        for role in ROLES:
            template = (TEMPLATES_DIR / f"{role}.txt").read_text()
            filled = (
                template
                .replace("{{PODCAST_CONCEPT}}", proposal.podcast_concept)
                .replace("{{PODCAST_TITLE}}", proposal.podcast_title)
                .replace("{{PODCAST_CONCEPT_DESCRIPTION}}", proposal.podcast_concept_description)
                .replace("{{HOST_DEFINITIONS}}", host_definitions)
            )
            out_path = OUTPUT_DIR / f"{role}.txt"
            out_path.write_text(filled)
            written.append(out_path.relative_to(WORKING_DIR).as_posix())

        report_lines = [
            f"Show: {proposal.podcast_concept}",
            f"Title: {proposal.podcast_title}",
            f"Hosts: {', '.join(proposal.hosts)}",
            "Artifacts written:",
            *(f"  - {p}" for p in written),
        ]
        await ctx.yield_output("\n".join(report_lines))


def build_workflow():
    builder_executor = AgentExecutor(agent=setup_builder_agent(), id="builder_executor")
    template_executor = TemplateExecutor(id="template_executor")
    review_executor = ReviewExecutor(
        id="review_executor",
        builder_agent_id="builder_executor",
        template_executor_id="template_executor",
    )

    return (
        WorkflowBuilder(start_executor=builder_executor)
        .add_edge(builder_executor, review_executor)
        .add_edge(review_executor, builder_executor)   # revise loop
        .add_edge(review_executor, template_executor)  # approval path
        .build()
    )


# Module-level workflow for runners (devui, etc.) that import `workflow`.
workflow = build_workflow()
