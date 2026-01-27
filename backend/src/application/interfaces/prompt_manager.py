"""Prompt manager interface for centralized prompt management."""

from abc import ABC, abstractmethod
from typing import Optional


class IPromptManager(ABC):
    """
    Abstract interface for prompt management.
    
    This interface provides centralized access to prompt templates.
    """
    
    @abstractmethod
    def get_question_prompt(
        self,
        user_profile_summary: str,
        conversation_history: str,
    ) -> str:
        """
        Get prompt for question agent.
        
        Args:
            user_profile_summary: Summary of user's current profile
            conversation_history: Recent conversation context
            
        Returns:
            Formatted prompt for question selection
        """
        pass
    
    @abstractmethod
    def get_validation_prompt(
        self,
        user_profile_summary: str,
    ) -> str:
        """
        Get prompt for validation agent.
        
        Args:
            user_profile_summary: Summary of user's profile
            
        Returns:
            Formatted prompt for validation
        """
        pass
    
    @abstractmethod
    def get_analysis_prompt(
        self,
        user_profile_summary: str,
    ) -> str:
        """
        Get prompt for analysis agent.
        
        Args:
            user_profile_summary: Complete user profile information
            
        Returns:
            Formatted prompt for property analysis and recommendations
        """
        pass
    
    @abstractmethod
    def get_system_message(self, agent_type: str) -> str:
        """
        Get system message for specific agent type.
        
        Args:
            agent_type: Type of agent (question, validation, analysis)
            
        Returns:
            System message for the agent
        """
        pass
