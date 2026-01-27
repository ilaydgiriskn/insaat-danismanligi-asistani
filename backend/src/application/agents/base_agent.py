"""Base agent class for common agent functionality."""

from abc import ABC, abstractmethod
from typing import Optional

from application.interfaces import ILLMService, IPromptManager
from infrastructure.config import get_logger


class BaseAgent(ABC):
    """
    Base class for all agents.
    
    Provides common functionality and enforces agent contract.
    """
    
    def __init__(
        self,
        llm_service: ILLMService,
        prompt_manager: IPromptManager,
    ):
        """
        Initialize base agent.
        
        Args:
            llm_service: LLM service for generating responses
            prompt_manager: Prompt manager for templates
        """
        self.llm_service = llm_service
        self.prompt_manager = prompt_manager
        self.logger = get_logger(self.__class__.__name__)
    
    @abstractmethod
    async def execute(self, *args, **kwargs) -> dict:
        """
        Execute agent logic.
        
        This method must be implemented by all agents.
        
        Returns:
            Agent execution result
        """
        pass
    
    def _log_execution(self, message: str) -> None:
        """Log agent execution."""
        self.logger.info(f"[{self.__class__.__name__}] {message}")
    
    def _log_error(self, error: Exception) -> None:
        """Log agent error."""
        self.logger.error(
            f"[{self.__class__.__name__}] Error: {str(error)}",
            exc_info=True
        )
