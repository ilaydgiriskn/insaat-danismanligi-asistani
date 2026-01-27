"""LLM service interface for dependency inversion."""

from abc import ABC, abstractmethod
from typing import Optional


class ILLMService(ABC):
    """
    Abstract interface for LLM service.
    
    This interface allows the application layer to use LLM functionality
    without depending on specific implementations (LangChain, OpenAI, etc.).
    """
    
    @abstractmethod
    async def generate_response(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> str:
        """
        Generate a response from the LLM.
        
        Args:
            prompt: User prompt or question
            system_message: Optional system message for context
            temperature: Sampling temperature (0.0 to 1.0)
            max_tokens: Maximum tokens in response
            
        Returns:
            Generated response text
        """
        pass
    
    @abstractmethod
    async def generate_structured_response(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        response_format: Optional[dict] = None,
    ) -> dict:
        """
        Generate a structured response (JSON) from the LLM.
        
        Args:
            prompt: User prompt or question
            system_message: Optional system message
            response_format: Expected response structure
            
        Returns:
            Structured response as dictionary
        """
        pass
