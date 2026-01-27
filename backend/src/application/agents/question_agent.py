"""Question agent for selecting next question to ask user."""

from typing import Optional

from application.agents.base_agent import BaseAgent
from domain.entities import UserProfile, Conversation
from domain.enums import QuestionCategory


class QuestionAgent(BaseAgent):
    """
    Agent responsible for selecting the next question to ask the user.
    
    This agent:
    1. Analyzes user's current profile
    2. Identifies missing information
    3. Selects the most relevant next question
    4. Ensures no question is repeated
    """
    
    async def execute(
        self,
        user_profile: UserProfile,
        conversation: Conversation,
    ) -> dict:
        """
        Select next question for the user.
        
        Args:
            user_profile: Current user profile
            conversation: Conversation history
            
        Returns:
            Dict with 'question' and 'category' keys
        """
        try:
            self._log_execution("Selecting next question")
            
            # Get unanswered categories
            unanswered = user_profile.get_unanswered_categories()
            
            if not unanswered:
                return {
                    "question": None,
                    "category": None,
                    "message": "All categories answered"
                }
            
            # Build context
            profile_summary = self._build_profile_summary(user_profile)
            conversation_history = self._build_conversation_history(conversation)
            
            # Get prompt
            prompt = self.prompt_manager.get_question_prompt(
                user_profile_summary=profile_summary,
                conversation_history=conversation_history,
            )
            
            system_message = self.prompt_manager.get_system_message("question")
            
            # Generate question using LLM
            response = await self.llm_service.generate_structured_response(
                prompt=prompt,
                system_message=system_message,
                response_format={
                    "question": "string",
                    "category": "string",
                    "reasoning": "string"
                }
            )
            
            self._log_execution(f"Generated question for category: {response.get('category')}")
            
            return {
                "question": response.get("question"),
                "category": response.get("category"),
                "reasoning": response.get("reasoning"),
            }
            
        except Exception as e:
            self._log_error(e)
            # Fallback to simple question selection
            return self._fallback_question_selection(unanswered)
    
    def _build_profile_summary(self, user_profile: UserProfile) -> str:
        """Build a summary of user's current profile."""
        parts = []
        
        if user_profile.name:
            parts.append(f"Name: {user_profile.name}")
        
        if user_profile.email:
            parts.append(f"Email: {user_profile.email}")
        
        if user_profile.phone:
            parts.append(f"Phone: {user_profile.phone}")
        
        if user_profile.hometown:
            parts.append(f"Hometown: {user_profile.hometown}")
        
        if user_profile.profession:
            parts.append(f"Profession: {user_profile.profession}")
        
        if user_profile.marital_status:
            parts.append(f"Marital Status: {user_profile.marital_status}")
        
        if user_profile.has_children is not None:
            parts.append(f"Has Children: {user_profile.has_children}")
        
        if user_profile.estimated_salary:
            parts.append(f"Estimated Salary: {user_profile.estimated_salary}")
            
        if user_profile.hobbies:
            parts.append(f"Hobbies: {', '.join(user_profile.hobbies)}")
            
        if user_profile.lifestyle_notes:
            parts.append(f"Lifestyle Notes: {user_profile.lifestyle_notes}")

        if user_profile.budget:
            parts.append(f"Budget: {user_profile.budget}")
        
        if user_profile.location:
            parts.append(f"Location: {user_profile.location}")
        
        if user_profile.property_preferences:
            parts.append(f"Property: {user_profile.property_preferences}")
        
        if user_profile.family_size:
            parts.append(f"Family size: {user_profile.family_size}")
        
        answered = [cat.value for cat in user_profile.answered_categories]
        parts.append(f"Answered categories: {', '.join(answered)}")
        
        return "\n".join(parts) if parts else "No information yet"
    
    def _build_conversation_history(self, conversation: Conversation) -> str:
        """Build conversation history summary."""
        recent_messages = conversation.get_recent_messages(5)
        
        if not recent_messages:
            return "No conversation history"
        
        history = []
        for msg in recent_messages:
            history.append(f"{msg.role.value}: {msg.content}")
        
        return "\n".join(history)
    
    def _fallback_question_selection(
        self,
        unanswered: set[QuestionCategory]
    ) -> dict:
        """Fallback question selection without LLM."""
        # Introduction Phase Priority
        intro_priority = [
            QuestionCategory.NAME,
            QuestionCategory.EMAIL,
            QuestionCategory.HOMETOWN,
            QuestionCategory.PROFESSION,
            QuestionCategory.MARITAL_STATUS,
            QuestionCategory.CHILDREN,
            QuestionCategory.SALARY,
            QuestionCategory.HOBBIES,
            QuestionCategory.PETS,
            QuestionCategory.PHONE,
        ]
        
        # Property Search Phase Priority
        property_priority = [
            QuestionCategory.BUDGET,
            QuestionCategory.LOCATION,
            QuestionCategory.PROPERTY_TYPE,
            QuestionCategory.ROOMS,
            QuestionCategory.FAMILY_SIZE,
        ]
        
        # Try introduction phase first
        for category in intro_priority:
            if category in unanswered:
                question = self._get_default_question(category)
                return {
                    "question": question,
                    "category": category.value,
                    "reasoning": "Introduction phase"
                }
        
        # Then property search phase
        for category in property_priority:
            if category in unanswered:
                question = self._get_default_question(category)
                return {
                    "question": question,
                    "category": category.value,
                    "reasoning": "Property search phase"
                }
        
        # If none in priority, pick first available
        category = next(iter(unanswered))
        question = self._get_default_question(category)
        return {
            "question": question,
            "category": category.value,
            "reasoning": "Fallback selection"
        }
    
    def _get_default_question(self, category: QuestionCategory) -> str:
        """Get default question for a category."""
        questions = {
            # Introduction Phase
            QuestionCategory.NAME: "İsminizi öğrenebilir miyim?",
            QuestionCategory.EMAIL: "Size ulaşabilmem için e-posta adresinizi alabilir miyim?",
            QuestionCategory.PHONE: "Telefon numaranızı da paylaşmak ister misiniz?",
            QuestionCategory.HOMETOWN: "Hangi şehirde doğup büyüdünüz?",
            QuestionCategory.PROFESSION: "Ne iş yapıyorsunuz?",
            QuestionCategory.MARITAL_STATUS: "Medeni durumunuz nedir?",
            QuestionCategory.CHILDREN: "Çocuğunuz var mı?",
            QuestionCategory.SALARY: "Aylık geliriniz ne kadar? (Tahmini olarak söyleyebilirsiniz)",
            QuestionCategory.HOBBIES: "Boş zamanlarınızda neler yapmayı seversiniz?",
            QuestionCategory.PETS: "Evcil hayvanınız var mı? Kedi, köpek gibi?",
            
            # Property Search Phase
            QuestionCategory.BUDGET: "Ev almak için bütçeniz ne kadar?",
            QuestionCategory.LOCATION: "Hangi şehir ve bölgede ev aramak istersiniz?",
            QuestionCategory.PROPERTY_TYPE: "Ne tür bir konut arıyorsunuz? (Daire, villa, müstakil ev vb.)",
            QuestionCategory.ROOMS: "Kaç oda istiyorsunuz?",
            QuestionCategory.FAMILY_SIZE: "Kaç kişilik bir aile için ev arıyorsunuz?",
        }
        
        return questions.get(
            category,
            f"{category.value} hakkında bilgi verebilir misiniz?"
        )
