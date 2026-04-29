"""Factory for creating Agent Framework agents with different model providers.

Supports Ollama, GitHub Copilot, and Foundry backends via the
MODEL_PROVIDER environment variable.

Environment variables per provider:

  ollama:
    OLLAMA_HOST           - Ollama server URL (default: http://localhost:11434)
    OLLAMA_CHAT_MODEL_ID  - Model name (e.g. gemma4:e4b)

  github-copilot:
    GITHUB_COPILOT_MODEL  - Model to use (e.g. gpt-5, claude-sonnet-4)

  foundry:
    FOUNDRY_PROJECT_ENDPOINT - Foundry project endpoint URL
    FOUNDRY_MODEL            - Model name (e.g. gpt-4o-mini)
"""

import os
from dataclasses import dataclass, field
from typing import Any


@dataclass
class AgentOptions:
    """Common options for creating an agent across all providers."""
    name: str = "Agent"
    instructions: str = "You are a helpful assistant."
    tools: list[Any] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


def create_agent(options: AgentOptions | None = None):
    """Create an agent using the provider specified by MODEL_PROVIDER env var.

    Args:
        options: Agent configuration. Uses defaults if not provided.

    Returns:
        An agent instance.

    Raises:
        ValueError: If MODEL_PROVIDER is not set or not recognized.
    """
    if options is None:
        options = AgentOptions()

    provider = os.getenv("MODEL_PROVIDER", "").lower()

    if provider == "ollama":
        return _create_ollama_agent(options)
    elif provider == "github-copilot":
        return _create_github_copilot_agent(options)
    elif provider == "foundry":
        return _create_foundry_agent(options)
    else:
        supported = ["ollama", "github-copilot", "foundry"]
        raise ValueError(
            f"MODEL_PROVIDER={provider!r} is not supported. "
            f"Set MODEL_PROVIDER to one of: {', '.join(supported)}"
        )


def _create_ollama_agent(options: AgentOptions):
    from agent_framework.ollama import OllamaChatClient

    client = OllamaChatClient(model=os.getenv("OLLAMA_CHAT_MODEL_ID"))
    return client.as_agent(
        name=options.name,
        instructions=options.instructions,
        tools=options.tools,
        **options.extra,
    )


def _create_github_copilot_agent(options: AgentOptions):
    from agent_framework_github_copilot import GitHubCopilotAgent

    default_options = {
        "instructions": options.instructions,
        **options.extra,
    }

    model = os.getenv("GITHUB_COPILOT_MODEL")
    if model:
        default_options["model"] = model

    return GitHubCopilotAgent(
        default_options=default_options,
        tools=options.tools or None,
    )


def _create_foundry_agent(options: AgentOptions):
    from agent_framework import Agent
    from agent_framework.foundry import FoundryChatClient

    api_key = os.getenv("FOUNDRY_API_KEY")
    if api_key:
        from azure.core.credentials import AccessToken
        from azure.core.credentials_async import AsyncTokenCredential

        class _ApiKeyCredential(AsyncTokenCredential):
            """Wraps an API key as a TokenCredential for Foundry."""
            async def get_token(self, *scopes, **kwargs):
                return AccessToken(api_key, 0)
            async def close(self): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass

        credential = _ApiKeyCredential()
    else:
        from azure.identity import AzureCliCredential
        credential = AzureCliCredential()

    client = FoundryChatClient(
        project_endpoint=os.getenv("FOUNDRY_PROJECT_ENDPOINT"),
        model=os.getenv("FOUNDRY_MODEL"),
        credential=credential,
    )

    return Agent(
        client=client,
        name=options.name,
        instructions=options.instructions,
        tools=options.tools,
        **options.extra,
    )
