# Copyright (c) Microsoft. All rights reserved.
"""Web search agent for Agent Framework Debug UI.

This agent is equipped with web search capabilities.
"""

import os
import json
import requests

from typing import Annotated
from pathlib import Path
from dotenv import load_dotenv
from pydantic import Field

from agent_factory import create_agent, AgentOptions

load_dotenv()

def web_search(
    query: Annotated[str, Field(description="Search query")],
) -> str:
    """Perform web search using Ollama API."""

    api_key = os.getenv("OLLAMA_API_KEY")
    if not api_key:
        return "Error: OLLAMA_API_KEY environment variable not set"

    url = "https://ollama.com/api/web_search"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    data = {
        "query": query
    }

    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        raw = json.loads(response.text)
        # Take top 3 results with just title and content snippet
        top_results = [
            {"title": r.get("title", ""), "content": r.get("content", "")[:4000]}
            for r in raw.get("results", [])[:3]
        ]
        result = json.dumps(top_results, indent=2)
        print(result.length)
        return result
    except requests.exceptions.RequestException as e:
        return f"Error fetching web content: {str(e)}"

def setup_agent():
    """Setup the web search agent."""

    agent = create_agent(AgentOptions(
        name="SearchAgent",
        instructions="You are a search assistant. When the user asks a question, use the web_search tool to find the answer. Answer the user's original question after receiving search results.",
        tools=[web_search],
    ))
    
    return agent

def main():
    """Launch the web search agent in DevUI."""
    import logging
    from agent_framework.devui import serve

    # Setup logging
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logger = logging.getLogger(__name__)
    

    logger.info("Starting Ollama Web Search Agent")
    logger.info("Available at: http://localhost:8090")
    logger.info("Entity ID: SearchAgent")
    logger.info("Note: Make sure OLLAMA_CHAT_MODEL_ID and OLLAMA_API_KEY are set in environment variables")

    # Setup agent
    agent = setup_agent()

    # Launch server with the agent
    serve(entities=[agent], port=8090, auto_open=True, instrumentation_enabled=True)

if __name__ == "__main__":
    main()
