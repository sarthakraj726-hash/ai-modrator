"""Model router selecting optimal models by task tier and fallback chains."""

from app.ai.models import ModelTier, TaskType
from app.core.config import Settings, get_settings


class ModelRouter:
    """
    Routes AI tasks to appropriate model candidates based on tier,
    ensuring cost optimization for simple tasks and high accuracy for complex ones.
    """

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def get_models_for_tier(self, tier: ModelTier) -> list[str]:
        """Return ordered list of primary and fallback model identifiers for given tier."""
        primary = self.settings.OPENROUTER_MODEL_PRIMARY
        fast = self.settings.OPENROUTER_MODEL_FAST
        fallback = self.settings.OPENROUTER_MODEL_FALLBACK
        reasoning = self.settings.OPENROUTER_MODEL_REASONING

        if tier == ModelTier.FAST:
            candidates = [fast, primary, fallback]
        elif tier == ModelTier.BALANCED:
            candidates = [primary, fast, fallback]
        elif tier == ModelTier.HIGH_ACCURACY:
            candidates = [primary, fallback, fast]
        elif tier == ModelTier.REASONING:
            candidates = [reasoning, primary, fallback]
        else:
            candidates = [fallback, primary, fast]

        # Deduplicate while preserving order and filter out empty strings
        return list(dict.fromkeys([m for m in candidates if m and m.strip()]))

    def get_tier_for_task(self, task_type: TaskType) -> ModelTier:
        """Map task type to recommended model performance tier."""
        if task_type == TaskType.MODERATION_CLASSIFY:
            return ModelTier.FAST
        elif task_type == TaskType.COHOST_REPLY:
            return ModelTier.BALANCED
        elif task_type == TaskType.CONTEXT_ANALYZE:
            return ModelTier.HIGH_ACCURACY
        elif task_type == TaskType.SUMMARIZE:
            return ModelTier.FAST
        return ModelTier.BALANCED


_global_model_router: ModelRouter | None = None


def get_model_router() -> ModelRouter:
    """Return singleton ModelRouter."""
    global _global_model_router
    if _global_model_router is None:
        _global_model_router = ModelRouter()
    return _global_model_router
