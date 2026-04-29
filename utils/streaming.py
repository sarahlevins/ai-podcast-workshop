from typing import AsyncIterable


async def stream_response(stream: AsyncIterable) -> str:
    """Print agent stream chunks as they arrive and return the full text."""
    chunks: list[str] = []
    async for event in stream:
        text = getattr(event, "text", None) or str(event)
        print(text, end="", flush=True)
        chunks.append(text)
    print()
    return "".join(chunks)
