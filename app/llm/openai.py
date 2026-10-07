import json
from typing import Any, AsyncGenerator, Dict, List, Optional
from openai import AsyncOpenAI
from app.core.config import settings
from app.core.logging import logger
from app.llm.base import LLMProvider


class OpenAILLMProvider(LLMProvider):
    """
    OpenAI gpt-4o-mini streaming LLM provider with function calling.
    Emits token events as they arrive, and tool_call events when function arguments finish streaming.
    """

    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model = model or settings.LLM_MODEL
        self.client = AsyncOpenAI(api_key=self.api_key) if self.api_key else None

    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        if not self.client:
            # Unified simulated conversational responses for offline test modes
            from app.llm.gemini import GeminiLLMProvider
            simulated_response = GeminiLLMProvider()._simulate_response(messages)
            for chunk in simulated_response:
                yield chunk
            return

        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "temperature": 0.3
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = "auto"

        tool_calls_accumulator: Dict[int, Dict[str, Any]] = {}

        try:
            stream = await self.client.chat.completions.create(**kwargs)
            async for chunk in stream:
                if not chunk.choices:
                    continue
                delta = chunk.choices[0].delta

                # Text token
                if delta.content:
                    yield {"type": "token", "content": delta.content}

                # Tool call chunks
                if delta.tool_calls:
                    for tc in delta.tool_calls:
                        idx = tc.index
                        if idx not in tool_calls_accumulator:
                            tool_calls_accumulator[idx] = {
                                "id": tc.id or "",
                                "name": tc.function.name if tc.function and tc.function.name else "",
                                "arguments_str": ""
                            }
                        if tc.id:
                            tool_calls_accumulator[idx]["id"] = tc.id
                        if tc.function and tc.function.name:
                            tool_calls_accumulator[idx]["name"] = tc.function.name
                        if tc.function and tc.function.arguments:
                            tool_calls_accumulator[idx]["arguments_str"] += tc.function.arguments

            # Yield complete tool calls
            for idx, tc_data in tool_calls_accumulator.items():
                try:
                    args = json.loads(tc_data["arguments_str"]) if tc_data["arguments_str"] else {}
                except json.JSONDecodeError:
                    args = {}
                yield {
                    "type": "tool_call",
                    "id": tc_data["id"],
                    "name": tc_data["name"],
                    "arguments": args
                }

        except Exception as exc:
            logger.error(f"OpenAI LLM streaming error: {exc}", exc_info=True)
            from app.llm.gemini import GeminiLLMProvider
            for chunk in GeminiLLMProvider()._simulate_response(messages):
                yield chunk

    def _simulate_response(self, messages_or_prompt: Any) -> List[Dict[str, Any]]:
        """Provides simulated dialogue and tool calling when running in offline mode."""
        from app.llm.gemini import GeminiLLMProvider
        return GeminiLLMProvider()._simulate_response(messages_or_prompt)
