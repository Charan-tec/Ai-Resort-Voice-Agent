from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator, Dict, List, Optional


class LLMProvider(ABC):
    """Abstract interface for streaming LLM providers supporting function calling."""

    @abstractmethod
    async def stream_chat(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Dict[str, Any]]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Yields stream events:
          {"type": "token", "content": "..."}
          {"type": "tool_call", "id": "...", "name": "...", "arguments": {...}}
        """
        pass
