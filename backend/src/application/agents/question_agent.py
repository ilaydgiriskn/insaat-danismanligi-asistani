"""Question agent for selecting next question to ask user."""

from typing import Optional
import random

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
            
            # Use deterministic fallback
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
        
        # Priority order (NAME is captured from first message)
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
                question = self._get_natural_question(user_profile, category)
                return {
                    "question": question,
                    "category": category.value,
                    "reasoning": "Priority-based selection"
                }
        
        if QuestionCategory.NAME in unanswered:
            return {
                "question": "İsminizi öğrenebilir miyim?",
                "category": QuestionCategory.NAME.value,
                "reasoning": "Fallback to name"
            }
        
        return {
            "question": None,
            "category": None,
            "message": "All priority categories answered"
        }
    
    def _get_natural_question(self, user_profile: UserProfile, category: QuestionCategory) -> str:
        """Get natural, varied questions based on category and context."""
        name = user_profile.name or ""
        
        # Varied connectors for natural flow
        connectors = ["Peki", "Şimdi", "Harika", "Anladım", "Güzel"]
        connector = random.choice(connectors)
        
        questions = {
            QuestionCategory.NAME: "İsminizi öğrenebilir miyim?",
            
            QuestionCategory.EMAIL: [
                f"Memnun oldum {name}! E-posta adresinizi alabilir miyim?",
                f"Güzel tanıştığımıza {name}! Mail adresiniz nedir?",
            ],
            
            QuestionCategory.PHONE: [
                f"{connector}, telefon numaranızı da paylaşır mısınız?",
                "Telefon numaranızı da alabilir miyim?",
            ],
            
            QuestionCategory.HOMETOWN: [
                f"{connector} {name}, nereli olduğunuzu sorabilir miyim?",
                f"Memleket neresi {name}?",
                "Hangi şehirde doğdunuz?",
            ],
            
            QuestionCategory.PROFESSION: [
                f"{connector}, ne iş yapıyorsunuz {name}?",
                "Mesleğiniz nedir?",
                f"Hangi sektörde çalışıyorsunuz {name}?",
            ],
            
            QuestionCategory.MARITAL_STATUS: [
                "Medeni durumunuz nedir?",
                "Evli misiniz, bekar mı?",
            ],
            
            QuestionCategory.CHILDREN: [
                "Çocuğunuz var mı?",
                "Çocuk sahibi misiniz?",
            ],
            
            QuestionCategory.SALARY: [
                f"{connector}, aylık geliriniz ne kadar? Tahmini söyleyebilirsiniz.",
                "Gelir durumunuz hakkında bilgi verir misiniz?",
            ],
            
            QuestionCategory.HOBBIES: [
                f"Boş zamanlarınızda neler yapmayı seviyorsunuz {name}?",
                "Hobileriniz neler?",
            ],
            
            QuestionCategory.PETS: [
                "Evcil hayvanınız var mı? Kedi, köpek gibi?",
                "Hayvan beslemeyi sever misiniz?",
            ],
            
            QuestionCategory.BUDGET: [
                f"Şimdi ev aramaya geçelim {name}! Bütçeniz ne kadar?",
                f"Ev için ayırabileceğiniz bütçe nedir {name}?",
                "Minimum ve maksimum ne kadar harcamak istersiniz?",
            ],
            
            QuestionCategory.LOCATION: [
                f"Hangi şehirde ev arıyorsunuz {name}?",
                "Tercih ettiğiniz konum veya semt var mı?",
                "Nerede oturmak istiyorsunuz?",
            ],
            
            QuestionCategory.PROPERTY_TYPE: [
                "Ne tür bir ev arıyorsunuz? Daire, villa, müstakil ev?",
                f"Daire mi, müstakil ev mi tercih edersiniz {name}?",
            ],
            
            QuestionCategory.ROOMS: [
                "Kaç odalı bir ev düşünüyorsunuz?",
                "Oda sayısı olarak ne tercih edersiniz? 2+1, 3+1 gibi?",
            ],
            
            QuestionCategory.FAMILY_SIZE: [
                f"Kaç kişi yaşayacaksınız bu evde {name}?",
                "Aile büyüklüğünüz nedir?",
            ],
        }
        
        question_options = questions.get(category)
        
        if isinstance(question_options, list):
            return random.choice(question_options)
        elif question_options:
            return question_options
        else:
            return f"{category.value} hakkında bilgi verir misiniz?"
