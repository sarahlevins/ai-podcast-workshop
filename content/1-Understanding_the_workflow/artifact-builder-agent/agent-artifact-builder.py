"""
Artifact Builder - Console Application

Interactively creates podcast agent artifacts from templates based on a user-provided concept.
"""

import asyncio
import sys

from agent_framework import WorkflowEvent, WorkflowRunState
from workflow import workflow, HostApprovalRequest


class Colors:
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    CYAN = "\033[96m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def show_loading(message="Processing"):
    sys.stdout.write(f"{Colors.YELLOW}{message}... {Colors.RESET}")
    sys.stdout.flush()


def clear_loading():
    sys.stdout.write("\r" + " " * 80 + "\r")
    sys.stdout.flush()


async def main():
    print("=" * 60)
    print("Agent Artifact Builder")
    print("=" * 60)
    print()

    concept = input("Describe your podcast concept: ").strip()
    if not concept:
        print("No concept provided. Exiting...")
        return

    print(f"\nStarting workflow for: {concept}")
    print("-" * 60)

    current_executor = None
    loading_shown = False
    workflow_complete = False
    pending_responses = None

    while not workflow_complete:
        # Start or continue the workflow
        if pending_responses:
            stream = workflow.run(responses=pending_responses, stream=True)
        else:
            stream = workflow.run(message=concept, stream=True)

        pending_responses = None

        async for event in stream:
            # Agent streaming data (text chunks)
            if event.type == "data":
                executor_id = event.executor_id

                if executor_id != current_executor:
                    if loading_shown:
                        clear_loading()
                        loading_shown = False
                    current_executor = executor_id
                    print(f"\n{Colors.BOLD}[{executor_id.upper()}]:{Colors.RESET}")

                text = getattr(event.data, "text", None)
                if text:
                    if loading_shown:
                        clear_loading()
                        loading_shown = False
                    print(f"{Colors.GREEN}{text}{Colors.RESET}", end="", flush=True)

            # Host approval request
            elif event.type == "request_info":
                if loading_shown:
                    clear_loading()
                    loading_shown = False

                if isinstance(event.data, HostApprovalRequest):
                    print("\n")
                    print("-" * 60)
                    print(f"{Colors.CYAN}{Colors.BOLD}HOST REVIEW{Colors.RESET}")
                    print("-" * 60)
                    print(f"{Colors.GREEN}{event.data.proposed_hosts}{Colors.RESET}")
                    print("-" * 60)
                    print(f"{Colors.YELLOW}{event.data.prompt}{Colors.RESET}")

                    user_response = input(f"{Colors.CYAN}Your response: {Colors.RESET}").strip()
                    pending_responses = {event._request_id: user_response}

                    print(f"\n{Colors.YELLOW}Continuing...{Colors.RESET}")
                    show_loading("Processing")
                    loading_shown = True

            # Final workflow output
            elif event.type == "output":
                if loading_shown:
                    clear_loading()
                    loading_shown = False

                print("\n")
                print("=" * 60)
                print(f"{Colors.BOLD}{Colors.GREEN}ARTIFACTS COMPLETE{Colors.RESET}")
                print("=" * 60)
                print(f"\n{Colors.GREEN}{event.data}{Colors.RESET}")
                workflow_complete = True

            # Workflow status
            elif event.type == "status":
                if event.state == WorkflowRunState.IDLE:
                    workflow_complete = True

            # Executor lifecycle (show loading)
            elif event.type == "executor_invoked":
                if not loading_shown:
                    show_loading(f"Running {event.executor_id}")
                    loading_shown = True

    print("\nDone!")


if __name__ == "__main__":
    asyncio.run(main())
