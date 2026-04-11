"""LLM client for Ollama and OpenAI."""

import json
import asyncio
from typing import Optional
from pydantic import BaseModel


class LLMResponse(BaseModel):
    content: str
    model: str
    usage: Optional[dict] = None


class LLMClient:
    """Client for LLM providers."""

    def __init__(self, provider: str = "ollama", model: str = "llama3",
                 endpoint: Optional[str] = None, api_key: Optional[str] = None):
        self.provider = provider
        self.model = model
        self.endpoint = endpoint
        self.api_key = api_key

        self._aiohttp_session = None
        self._openai_client = None

        if provider in ("openai", "openrouter"):
            try:
                import openai
                from openai import AsyncOpenAI
                self._openai = openai
                self._openai_client = AsyncOpenAI(
                    api_key=self.api_key or "dummy",
                    base_url=self.endpoint or None
                )
            except ImportError:
                raise ImportError("openai package not installed")

    async def _get_aiohttp_session(self):
        if self._aiohttp_session is None or self._aiohttp_session.closed:
            import aiohttp
            self._aiohttp_session = aiohttp.ClientSession()
        return self._aiohttp_session

    async def chat(self, messages: list[dict], system: Optional[str] = None) -> LLMResponse:
        """Send chat request."""
        if self.provider == "ollama":
            return await self._ollama_chat(messages, system)
        elif self.provider in ("openai", "openrouter"):
            return await self._openai_chat(messages, system)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

    async def _ollama_chat(self, messages: list[dict], system: Optional[str]) -> LLMResponse:
        url = f"{self.endpoint or 'http://localhost:11434'}/api/chat"

        all_messages = []
        if system:
            all_messages.append({"role": "system", "content": system})
        all_messages.extend(messages)

        payload = {
            "model": self.model,
            "messages": all_messages,
            "stream": False
        }

        session = await self._get_aiohttp_session()
        async with session.post(url, json=payload) as resp:
            data = await resp.json()
            return LLMResponse(
                content=data.get("message", {}).get("content", ""),
                model=self.model
            )

    async def _openai_chat(self, messages: list[dict], system: Optional[str]) -> LLMResponse:
        all_messages = []
        if system:
            all_messages.append({"role": "system", "content": system})
        all_messages.extend(messages)

        response = await self._openai_client.chat.completions.create(
            model=self.model,
            messages=all_messages
        )
        return LLMResponse(
            content=response.choices[0].message.content,
            model=response.model,
            usage=response.usage.model_dump() if response.usage else None
        )

    async def close(self):
        """Clean up underlying HTTP connections."""
        if self._aiohttp_session and not self._aiohttp_session.closed:
            await self._aiohttp_session.close()
        if self._openai_client:
            await self._openai_client.close()
