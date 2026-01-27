"""Question agent for selecting next question to ask user."""

from typing import Optional

from application.agents.base_agent import BaseAgent
from domain.entities import UserProfile, Conversation
from domain.enums import QuestionCategory


class QuestionAgent(BaseAgent):
    """Agent that selects the next question to ask the user."""
    
    async def execute(
        self,
        user_profile: UserProfile,
        conversation: Conversation,
    ) -> dict:
        """Select next question based on missing profile information."""
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
            
            # ALWAYS use deterministic fallback - no LLM for question selection
            return self._fallback_question_selection(user_profile, unanswered)
            
        except Exception as e:
            self._log_error(e)
            unanswered = user_profile.get_unanswered_categories()
            return self._fallback_question_selection(user_profile, unanswered)
    
    def _fallback_question_selection(
        self,
        user_profile: UserProfile,
        unanswered: set[QuestionCategory]
    ) -> dict:
        """Deterministic question selection - no LLM, predictable order."""
        
        # SKIP NAME - it's captured directly from first message
        # Order: email -> hometown -> profession -> budget -> location -> property
        priority = [
            QuestionCategory.EMAIL,
            QuestionCategory.HOMETOWN,
            QuestionCategory.PROFESSION,
            QuestionCategory.MARITAL_STATUS,
            QuestionCategory.CHILDREN,
            QuestionCategory.BUDGET,
            QuestionCategory.LOCATION,
            QuestionCategory.PROPERTY_TYPE,
            QuestionCategory.ROOMS,
            QuestionCategory.FAMILY_SIZE,
            QuestionCategory.SALARY,
            QuestionCategory.HOBBIES,
            QuestionCategory.PETS,
            QuestionCategory.PHONE,
        ]
        
        for category in priority:
            if category in unanswered:
                question = self._get_personalized_question(user_profile, category)
                return {
                    "question": question,
                    "category": category.value,
                    "reasoning": "Priority-based selection"
                }
        
        # If NAME is still unanswered (shouldn't happen with new logic)
        if QuestionCategory.NAME in unanswered:
            question = self._get_personalized_question(user_profile, QuestionCategory.NAME)
            return {
                "question": question,
                "category": QuestionCategory.NAME.value,
                "reasoning": "Fallback to name"
            }
        
        return {
            "question": None,
            "category": None,
            "message": "All priority categories answered"
        }
    
    def _get_personalized_question(self, user_profile: UserProfile, category: QuestionCategory) -> str:
        """Get personalized question based on user's name."""
        name = user_profile.name or ""
        
        # Create friendly greeting with name
        if name:
            greeting = f"Teşekkürler {name}! "
        else:
            greeting = ""
        
        questions = {
            QuestionCategory.NAME: "İsminizi öğrenebilir miyim?",
            QuestionCategory.EMAIL: f"{greeting}Size ulaşabilmem için e-posta adresinizi alabilir miyim?",
            QuestionCategory.PHONE: f"{greeting}Telefon numaranızı da paylaşmak ister misiniz?",
            QuestionCategory.HOMETOWN: f"{greeting}Hangi şehirde doğup büyüdünüz?",
            QuestionCategory.PROFESSION: f"{greeting}Ne iş yapıyorsunuz?",
            QuestionCategory.MARITAL_STATUS: f"{greeting}Medeni durumunuz nedir?",
            QuestionCategory.CHILDREN: f"{greeting}Çocuğunuz var mı?",
            QuestionCategory.SALARY: f"{greeting}Aylık geliriniz ne kadar? (Tahmini olarak söyleyebilirsiniz)",
            QuestionCategory.HOBBIES: f"{greeting}Boş zamanlarınızda neler yapmayı seversiniz?",
            QuestionCategory.PETS: f"{greeting}Evcil hayvanınız var mı?",
            QuestionCategory.BUDGET: f"{greeting}Ev almak için bütçeniz ne kadar?",
            QuestionCategory.LOCATION: f"{greeting}Hangi şehir veya bölgede ev aramak istiyorsunuz?",
            QuestionCategory.PROPERTY_TYPE: f"{greeting}Ne tür bir konut arıyorsunuz? (Daire, villa, müstakil ev gibi)",
            QuestionCategory.ROOMS: f"{greeting}Kaç odalı bir ev tercih edersiniz?",
            QuestionCategory.FAMILY_SIZE: f"{greeting}Kaç kişilik bir aile için ev arıyorsunuz?",
        }
        
        return questions.get(
            category,
            f"{greeting}{category.value} hakkında bilgi verebilir misiniz?"
        )
    
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
