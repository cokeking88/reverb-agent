"""LLM client for Ollama and OpenAI."""

import json
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
        
        if provider == "openai":
            try:
                import openai
                self._openai = openai
                openai.api_key = api_key or "dummy"
                if endpoint:
                    openai.base_url = endpoint
            except ImportError:
                raise ImportError("openai package not installed")
    
    async def chat(self, messages: list[dict], system: Optional[str] = None) -> LLMResponse:
        """Send chat request."""
        if self.provider == "ollama":
            return await self._ollama_chat(messages, system)
        elif self.provider == "openai":
            return await self._openai_chat(messages, system)
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")
    
    async def _ollama_chat(self, messages: list[dict], system: Optional[str]) -> LLMResponse:
        import aiohttp
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
        
        async with aiohttp.ClientSession() as session:
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
        
        response = await self._openai.ChatCompletion.acreate(
            model=self.model,
            messages=all_messages
        )
        return LLMResponse(
            content=response.choices[0].message.content,
            model=response.model,
            usage=response.usage.to_dict() if response.usage else None
        )