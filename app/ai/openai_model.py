import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()


class OpenAIModel:
    """
    Simple reusable OpenAI interaction class.

    Features:
    - required system prompt
    - persistent memory
    - usage metadata
    - response time tracking
    - context usage percentage
    - automatic memory reset when context gets too high
    """

    MODEL_CONTEXT_WINDOWS = {
        "gpt-5-mini": 400_000,
        "gpt-5-nano": 400_000,
        "gpt-5": 400_000,
    }

    CONTEXT_RESET_THRESHOLD_PERCENT = 90.0

    def __init__(
        self,
        system_prompt: str,
        model: str = "gpt-5-mini",
        api_key: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")

        if not self.api_key:
            raise ValueError("Missing OPENAI_API_KEY in environment or constructor.")

        if not system_prompt or not isinstance(system_prompt, str):
            raise ValueError("system_prompt is required and must be a string.")

        if not model or not isinstance(model, str):
            raise ValueError("model is required and must be a string.")

        self.model = model
        self.system_prompt = system_prompt
        self.client = OpenAI(api_key=self.api_key)

        self.memory: List[Dict[str, str]] = []
        self.last_warning: Optional[str] = None

    def run(self, user_message: str) -> Dict[str, Any]:
        if not user_message or not isinstance(user_message, str):
            raise ValueError("user_message is required and must be a non-empty string.")

        self.memory.append(
            {
                "role": "user",
                "content": user_message,
            }
        )

        started_at = time.perf_counter()

        response = self.client.responses.create(
            model=self.model,
            instructions=self.system_prompt,
            input=self.memory,
        )

        duration_seconds = round(time.perf_counter() - started_at, 3)

        answer = response.output_text

        self.memory.append(
            {
                "role": "assistant",
                "content": answer,
            }
        )

        usage_data = self._extract_usage(response)
        context_data = self._calculate_context_usage(usage_data)

        warning = None

        if self._should_reset_memory(context_data):
            warning = (
                "Context usage reached the reset threshold. "
                "Memory was reset after this response."
            )
            self.reset_memory()

        self.last_warning = warning

        return {
            "answer": answer,
            "metadata": {
                "model": self.model,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "duration_seconds": duration_seconds,
                "usage": usage_data,
                "context": context_data,
                "memory_messages": len(self.memory),
                "warning": warning,
            },
        }

    def reset_memory(self) -> None:
        self.memory = []

    def _extract_usage(self, response: Any) -> Dict[str, Optional[int]]:
        usage = getattr(response, "usage", None)

        if usage is None:
            return {
                "input_tokens": None,
                "output_tokens": None,
                "total_tokens": None,
            }

        return {
            "input_tokens": getattr(usage, "input_tokens", None),
            "output_tokens": getattr(usage, "output_tokens", None),
            "total_tokens": getattr(usage, "total_tokens", None),
        }

    def _calculate_context_usage(
        self,
        usage_data: Dict[str, Optional[int]],
    ) -> Dict[str, Optional[float]]:
        context_window = self.MODEL_CONTEXT_WINDOWS.get(self.model)
        total_tokens = usage_data.get("total_tokens")

        if not context_window or not total_tokens:
            return {
                "context_window": context_window,
                "context_used_percent": None,
                "reset_threshold_percent": self.CONTEXT_RESET_THRESHOLD_PERCENT,
            }

        return {
            "context_window": context_window,
            "context_used_percent": round((total_tokens / context_window) * 100, 4),
            "reset_threshold_percent": self.CONTEXT_RESET_THRESHOLD_PERCENT,
        }

    def _should_reset_memory(self, context_data: Dict[str, Optional[float]]) -> bool:
        context_used_percent = context_data.get("context_used_percent")

        if context_used_percent is None:
            return False

        return context_used_percent >= self.CONTEXT_RESET_THRESHOLD_PERCENT