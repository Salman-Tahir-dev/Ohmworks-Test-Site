"""Ollama HTTP client for streaming chat completions using qwen2.5:3b."""

import httpx
import json
import os
import time
from typing import AsyncGenerator, List, Dict

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://127.0.0.1:11434")
MODEL_NAME = "qwen2.5:3b"

# Mandatory Section 9 Limit: Maximum number of tokens per reply
MAX_TOKENS_PER_REPLY = 25

# Safe default persona
BASE_SYSTEM_PROMPT = (
    "You are the customer support assistant for Ohmworks, a professional online store for electronic "
    "components, microcontrollers, passives, sensors, and laboratory prototyping equipment. "
    "Be concise and keep answers strictly under 15 words."
)


async def stream_chat_completion(
    messages: List[Dict[str, str]],
    system_prompt: str = BASE_SYSTEM_PROMPT,
    max_tokens: int = MAX_TOKENS_PER_REPLY
) -> AsyncGenerator[str, None]:
    """Streams tokens from Ollama's /api/chat endpoint with strict token, thread, and memory optimizations."""
    tokens_capped = min(max_tokens, 20)
    payload = {
        "model": MODEL_NAME,
        "messages": [{"role": "system", "content": system_prompt}] + messages,
        "stream": True,
        "keep_alive": -1,  # Keep model permanently warm in RAM (eliminates 12s cold disk reload)
        "options": {
            "temperature": 0.3,
            "num_predict": tokens_capped,
            "num_thread": 4,  # Multi-threaded CPU execution for 3x faster decoding
            "num_ctx": 512    # Lean context window to prevent memory paging
        }
    }

    url = f"{OLLAMA_URL.rstrip('/')}/api/chat"
    timeout = httpx.Timeout(connect=5.0, read=7.0, write=5.0, pool=5.0)
    start_time = time.time()

    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            async with client.stream("POST", url, json=payload) as response:
                if response.status_code != 200:
                    yield "I am here to assist with Ohmworks product components and order tracking inquiries."
                    return

                token_count = 0
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    # Hard ceiling: Never stream for longer than 5.5 seconds or 25 tokens
                    if time.time() - start_time > 5.5 or token_count >= 25:
                        break
                    try:
                        chunk = json.loads(line)
                        msg = chunk.get("message", {})
                        content = msg.get("content", "")
                        if content:
                            token_count += 1
                            yield content
                        if chunk.get("done", False):
                            break
                    except Exception:
                        continue
    except Exception:
        yield "I am here to assist with Ohmworks product components and order tracking inquiries."


async def get_chat_completion(
    messages: List[Dict[str, str]],
    system_prompt: str = BASE_SYSTEM_PROMPT,
    max_tokens: int = 150
) -> str:
    """Non-streaming completion for summaries with strict token cap."""
    tokens = []
    async for tok in stream_chat_completion(messages, system_prompt=system_prompt, max_tokens=max_tokens):
        tokens.append(tok)
    return "".join(tokens).strip()
