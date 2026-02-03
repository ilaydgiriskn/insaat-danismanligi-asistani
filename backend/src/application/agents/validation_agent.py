"""Validation agent for checking if user profile is complete."""

from application.agents.base_agent import BaseAgent
from domain.entities import UserProfile


class ValidationAgent(BaseAgent):
    """
    Agent responsible for validating if user profile has sufficient information.
    
    This agent:
    1. Checks if minimum required fields are filled
    2. Validates data quality
    3. Determines if ready for analysis
    """
    
    async def execute(self, user_profile: UserProfile) -> dict:
        """
        Validate user profile completeness.
        
        Args:
            user_profile: User profile to validate
            
        Returns:
            Dict with 'is_valid', 'is_complete', 'missing_fields', 'message'
        """
        try:
            self._log_execution("Validating user profile")
            
            # Check basic completeness
            is_complete = user_profile.is_complete()
            
            if is_complete:
                # Use LLM for quality validation
                profile_summary = self._build_profile_summary(user_profile)
                prompt = self.prompt_manager.get_validation_prompt(profile_summary)
                system_message = self.prompt_manager.get_system_message("validation")
                
                # Get agent-specific settings
                from infrastructure.config import get_settings
                settings = get_settings()
                
                response = await self.llm_service.generate_structured_response(
                    prompt=prompt,
                    system_message=system_message,
                    response_format={
                        "is_valid": "boolean",
                        "is_ready_for_analysis": "boolean",
                        "missing_or_unclear": "array",
                        "message": "string"
                    },
                    temperature=settings.validation_agent_temperature,
                    max_tokens=settings.validation_agent_max_tokens,
                )
                
                self._log_execution(
                    f"Validation result: {response.get('is_ready_for_analysis')}"
                )
                
                return {
                    "is_valid": response.get("is_valid", True),
                    "is_complete": True,
                    "is_ready_for_analysis": response.get("is_ready_for_analysis", True),
                    "missing_fields": response.get("missing_or_unclear", []),
                    "message": response.get("message", "Profile is complete"),
                }
            else:
                # Not complete - return missing categories
                missing = user_profile.get_unanswered_categories()
                missing_list = [cat.value for cat in missing]
                
                return {
                    "is_valid": False,
                    "is_complete": False,
                    "is_ready_for_analysis": False,
                    "missing_fields": missing_list,
                    "message": f"Missing information: {', '.join(missing_list)}",
                }
                
        except Exception as e:
            self._log_error(e)
            # Fallback to basic validation
            return self._fallback_validation(user_profile)
    
    def _build_profile_summary(self, user_profile: UserProfile) -> str:
        """Build detailed profile summary for validation."""
        parts = []
        
        parts.append(f"User ID: {user_profile.id}")
        
        if user_profile.name:
            parts.append(f"Name: {user_profile.name}")
        
        if user_profile.budget:
            parts.append(
                f"Budget: {user_profile.budget.min_amount:,} - "
                f"{user_profile.budget.max_amount:,} {user_profile.budget.currency}"
            )
        
        if user_profile.location:
            parts.append(f"Location: {user_profile.location}")
        
        if user_profile.property_preferences:
            prefs = user_profile.property_preferences
            parts.append(f"Property Type: {prefs.property_type}")
            if prefs.min_rooms or prefs.max_rooms:
                parts.append(f"Rooms: {prefs.min_rooms} - {prefs.max_rooms}")
            if prefs.has_balcony is not None:
                parts.append(f"Balcony: {'Yes' if prefs.has_balcony else 'No'}")
            if prefs.has_parking is not None:
                parts.append(f"Parking: {'Yes' if prefs.has_parking else 'No'}")
        
        if user_profile.family_size:
            parts.append(f"Family Size: {user_profile.family_size}")
        
        answered = [cat.value for cat in user_profile.answered_categories]
        parts.append(f"Answered Categories: {', '.join(answered)}")
        
        return "\n".join(parts)
    
    def _fallback_validation(self, user_profile: UserProfile) -> dict:
        """Fallback validation without LLM."""
        is_complete = user_profile.is_complete()
        
        if is_complete:
            return {
                "is_valid": True,
                "is_complete": True,
                "is_ready_for_analysis": True,
                "missing_fields": [],
                "message": "Profile has minimum required information",
            }
        else:
            missing = user_profile.get_unanswered_categories()
            missing_list = [cat.value for cat in missing]
            
            return {
                "is_valid": False,
                "is_complete": False,
                "is_ready_for_analysis": False,
                "missing_fields": missing_list,
                "message": f"Missing: {', '.join(missing_list)}",
            }
