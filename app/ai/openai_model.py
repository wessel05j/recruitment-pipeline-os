import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv
from openai import OpenAI, RateLimitError

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
        use_memory: bool = True,
        max_retries: int = 3,
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
        self.use_memory = use_memory
        self.max_retries = max_retries

        self.memory: List[Dict[str, str]] = []
        self.last_warning: Optional[str] = None

    def run(self, user_message: str) -> Dict[str, Any]:
        if not user_message or not isinstance(user_message, str):
            raise ValueError("user_message is required and must be a non-empty string.")

        input_messages = self._build_input(user_message)

        started_at = time.perf_counter()

        response = self._create_response_with_retry(
            input_messages=input_messages,
        )

        duration_seconds = round(time.perf_counter() - started_at, 3)

        answer = response.output_text

        if self.use_memory:
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

    def _build_input(self, user_message: str) -> List[Dict[str, str]]:
        message = {
            "role": "user",
            "content": user_message,
        }

        if not self.use_memory:
            return [message]

        self.memory.append(message)
        return self.memory

    def _create_response_with_retry(
        self,
        input_messages: List[Dict[str, str]],
    ) -> Any:
        attempt = 0

        while True:
            try:
                return self.client.responses.create(
                    model=self.model,
                    instructions=self.system_prompt,
                    input=input_messages,
                )
            except RateLimitError as error:
                attempt += 1

                if attempt > self.max_retries:
                    raise

                delay = self._rate_limit_delay(error, attempt)
                print(
                    f"OpenAI rate limit reached. Waiting {round(delay, 1)}s before retry {attempt}/{self.max_retries}."
                )
                time.sleep(delay)

    def _rate_limit_delay(self, error: RateLimitError, attempt: int) -> float:
        message = str(error)
        match = re.search(r"try again in ([0-9.]+)s", message)

        if match:
            return max(float(match.group(1)) + 1.0, 1.0)

        return min(2.0 * attempt, 10.0)

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
