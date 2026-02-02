"""LangChain implementation of LLM service."""

import json
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage

from application.interfaces import ILLMService
from infrastructure.config import get_settings, get_logger


class LangChainService(ILLMService):
    """Concrete implementation of ILLMService using LangChain and OpenAI."""
    
    def __init__(self):
        """Initialize LangChain service."""
        self.settings = get_settings()
        self.logger = get_logger(self.__class__.__name__)
        
        self.llm = ChatOpenAI(
            model=self.settings.openai_model,
            temperature=self.settings.openai_temperature,
            max_tokens=self.settings.openai_max_tokens,
            openai_api_key=self.settings.openai_api_key,
            base_url=self.settings.openai_base_url,
        )
    
    async def generate_response(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 1000,
    ) -> str:
        """Generate a response from the LLM."""
        try:
            messages = []
            if system_message:
                messages.append(SystemMessage(content=system_message))
            
            messages.append(HumanMessage(content=prompt))
            
            # Use the existing LLM instance for consistency
            # Note: temperature and max_tokens are set at the LLM instance level in __init__
            # If you need to override them per call, you would pass them to ainvoke or re-initialize LLM
            response = await self.llm.ainvoke(messages)
            
            return response.content
            
        except Exception as e:
            self.logger.error(f"Error generating response: {str(e)}", exc_info=True)
            raise
    
    async def generate_structured_response(
        self,
        prompt: str,
        system_message: Optional[str] = None,
        response_format: Optional[dict] = None,
    ) -> dict:
        """Generate a structured response (JSON) from the LLM."""
        try:
            # Add JSON format instruction to prompt
            format_instruction = "\n\nRespond ONLY with valid JSON."
            if response_format:
                format_instruction += f"\n\nExpected format:\n{json.dumps(response_format, indent=2)}"
            
            full_prompt = prompt + format_instruction
            
            messages = []
            
            if system_message:
                messages.append(SystemMessage(content=system_message))
            
            messages.append(HumanMessage(content=full_prompt))
            
            response = await self.llm.ainvoke(messages)
            
            # Parse JSON response - Enhanced for deepseek-thinking model
            content = response.content.strip()
            
            # DeepSeek-Thinking model may include <think>...</think> blocks
            # Extract only the JSON part
            if "<think>" in content and "</think>" in content:
                # Remove thinking blocks
                import re
                content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
            
            # Try direct JSON parse first
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                # Try to extract JSON from response
                
                # Remove markdown code blocks if present
                if content.startswith("```json"):
                    content = content[7:]
                if content.startswith("```"):
                    content = content[3:]
                if content.endswith("```"):
                    content = content[:-3]
                
                content = content.strip()
                
                # Try to find JSON object in the content
                # Look for first { and last }
                start_idx = content.find('{')
                end_idx = content.rfind('}')
                
                if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                    json_str = content[start_idx:end_idx+1]
                    return json.loads(json_str)
                
                # If still fails, try the original content
                return json.loads(content)
                
        except Exception as e:
            self.logger.error(
                f"Error generating structured response: {str(e)}",
                exc_info=True
            )
            raise

