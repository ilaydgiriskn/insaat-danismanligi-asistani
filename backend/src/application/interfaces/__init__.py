"""Application interfaces - Port definitions for external services."""

from .llm_service import ILLMService
from .prompt_manager import IPromptManager

__all__ = ["ILLMService", "IPromptManager"]
