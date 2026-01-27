"""Analysis agent for generating property recommendations."""

from application.agents.base_agent import BaseAgent
from domain.entities import UserProfile


class AnalysisAgent(BaseAgent):
    """
    Agent responsible for analyzing user profile and generating recommendations.
    
    This agent:
    1. Analyzes complete user profile
    2. Generates property recommendations
    3. Provides reasoning and explanations
    """
    
    async def execute(self, user_profile: UserProfile) -> dict:
        """
        Generate property analysis and recommendations.
        
        Args:
            user_profile: Complete user profile
            
        Returns:
            Dict with 'recommendations', 'analysis', 'summary'
        """
        try:
            self._log_execution("Generating property analysis")
            
            # Build comprehensive profile summary
            profile_summary = self._build_detailed_profile(user_profile)
            
            # Get analysis prompt
            prompt = self.prompt_manager.get_analysis_prompt(profile_summary)
            system_message = self.prompt_manager.get_system_message("analysis")
            
            # Generate analysis using LLM
            response = await self.llm_service.generate_structured_response(
                prompt=prompt,
                system_message=system_message,
                response_format={
                    "summary": "string",
                    "recommendations": "array",
                    "key_considerations": "array",
                    "budget_analysis": "string",
                    "location_insights": "string",
                }
            )
            
            self._log_execution("Analysis completed successfully")
            
            return {
                "summary": response.get("summary", ""),
                "recommendations": response.get("recommendations", []),
                "key_considerations": response.get("key_considerations", []),
                "budget_analysis": response.get("budget_analysis", ""),
                "location_insights": response.get("location_insights", ""),
            }
            
        except Exception as e:
            self._log_error(e)
            # Fallback to basic analysis
            return self._fallback_analysis(user_profile)
    
    def _build_detailed_profile(self, user_profile: UserProfile) -> str:
        """Build comprehensive profile for analysis."""
        sections = []
        
        # Header
        sections.append("=== USER PROFILE ANALYSIS ===\n")
        
        # Budget
        if user_profile.budget:
            budget = user_profile.budget
            sections.append(f"BUDGET:")
            sections.append(f"  Range: {budget.min_amount:,} - {budget.max_amount:,} {budget.currency}")
            sections.append(f"  Average: {(budget.min_amount + budget.max_amount) / 2:,.0f} {budget.currency}")
            sections.append("")
        
        # Location
        if user_profile.location:
            loc = user_profile.location
            sections.append(f"LOCATION:")
            sections.append(f"  City: {loc.city}")
            if loc.district:
                sections.append(f"  District: {loc.district}")
            sections.append(f"  Country: {loc.country}")
            sections.append("")
        
        # Property Preferences
        if user_profile.property_preferences:
            prefs = user_profile.property_preferences
            sections.append(f"PROPERTY PREFERENCES:")
            sections.append(f"  Type: {prefs.property_type}")
            if prefs.min_rooms or prefs.max_rooms:
                sections.append(f"  Rooms: {prefs.min_rooms or 'any'} - {prefs.max_rooms or 'any'}")
            if prefs.has_balcony is not None:
                sections.append(f"  Balcony: {'Required' if prefs.has_balcony else 'Not required'}")
            if prefs.has_parking is not None:
                sections.append(f"  Parking: {'Required' if prefs.has_parking else 'Not required'}")
            sections.append("")
        
        # Family
        if user_profile.family_size:
            sections.append(f"FAMILY:")
            sections.append(f"  Size: {user_profile.family_size} people")
            sections.append("")
        
        return "\n".join(sections)
    
    def _fallback_analysis(self, user_profile: UserProfile) -> dict:
        """Fallback analysis without LLM."""
        recommendations = []
        
        # Basic recommendation based on profile
        if user_profile.property_preferences:
            prop_type = user_profile.property_preferences.property_type
            recommendations.append(
                f"Look for {prop_type.value} properties in your specified location"
            )
        
        if user_profile.budget:
            budget = user_profile.budget
            recommendations.append(
                f"Focus on properties within {budget.min_amount:,} - "
                f"{budget.max_amount:,} {budget.currency} range"
            )
        
        if user_profile.location:
            recommendations.append(
                f"Search in {user_profile.location.city} area"
            )
        
        return {
            "summary": "Basic property recommendations based on your profile",
            "recommendations": recommendations,
            "key_considerations": [
                "Verify property documents",
                "Check neighborhood amenities",
                "Consider future resale value"
            ],
            "budget_analysis": "Budget range is appropriate for the selected location",
            "location_insights": "Selected location offers good residential options",
        }
