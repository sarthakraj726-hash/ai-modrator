"""Abstract interface for AI/LLM providers."""

from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel

from app.ai.models import (
    ChatMessage,
    CompletionRequest,
    CompletionResponse,
    ModelTier,
)

T = TypeVar("T", bound=BaseModel)


class AIProvider(ABC):
    """
    Abstract provider interface for multi-model LLM generation,
    structured classification, and co-host dialogue synthesis.
    """

    @abstractmethod
    async def generate_completion(self, request: CompletionRequest) -> CompletionResponse:
        """Generate text completion for the provided message sequence."""
        pass

    @abstractmethod
    async def classify(
        self,
        messages: list[ChatMessage],
        response_model: type[T],
        model_tier: ModelTier = ModelTier.FAST,
    ) -> T:
        """Execute structured JSON completion parsed into the specified Pydantic schema."""
        pass

    @abstractmethod
    async def generate_reply(
        self,
        messages: list[ChatMessage],
        model_tier: ModelTier = ModelTier.BALANCED,
        max_tokens: int = 100,
    ) -> CompletionResponse:
        """Generate concise co-host response."""
        pass

    @abstractmethod
    async def summarize(self, text: str, max_words: int = 50) -> str:
        """Produce a brief natural-language summary of chat context."""
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        """Check provider connectivity and API key validity."""
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return identifier name for the provider."""
        pass
