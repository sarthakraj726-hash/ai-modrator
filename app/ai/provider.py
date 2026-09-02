"""Abstract interface for AI/LLM providers."""

from abc import ABC, abstractmethod

from app.ai.models import CompletionRequest, CompletionResponse


class AIProvider(ABC):
    """Abstract provider interface for multi-model LLM generation."""

    @abstractmethod
    async def generate_completion(self, request: CompletionRequest) -> CompletionResponse:
        """Generate text completion for the provided message sequence."""
        pass

    @abstractmethod
    def get_provider_name(self) -> str:
        """Return identifier name for the provider."""
        pass
