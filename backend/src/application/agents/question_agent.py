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
            QuestionCategory.NAME: "Sizi hangi isimle tanıyabilirim?",
            
            QuestionCategory.EMAIL: [
                f"Sizinle vizyoner paylaşımlar yapabileceğimiz bir mektup kutunuz (E-posta) var mı {name}?",
                f"Güzel tanıştığımıza {name}! Size özel notlar iletebileceğim bir adresiniz var mı?",
            ],
            
            QuestionCategory.PHONE: [
                f"{connector}, sizinle sesli veya anlık iletişim kurabileceğimiz bir numaranız var mı?",
                "Size ulaşabileceğim en doğru irtibat numarası nedir?",
            ],
            
            QuestionCategory.HOMETOWN: [
                f"{connector} {name}, kökleriniz hangi şehrin topraklarında, merak ettim?",
                f"Hangi rüzgarın estiği diyarlardan geliyorsunuz {name}?",
            ],
            
            QuestionCategory.PROFESSION: [
                f"{connector}, zamanınızı hangi değerleri üreterek geçiriyorsunuz {name}?",
                "Hangi uzmanlık alanı sizin tutkunuz oldu?",
            ],
            
            QuestionCategory.MARITAL_STATUS: [
                "Hayatın bu yolculuğuna tek başınıza mı yoksa değerli bir yol arkadaşıyla mı devam ediyorsunuz?",
                "Yaşam alanınızı kiminle paylaşma hayali kuruyorsunuz?",
            ],
            
            QuestionCategory.CHILDREN: [
                "Küçük kahkahaların yükseldiği bir yuva mı hayaliniz, yoksa daha dingin bir hayat mı?",
                "Ailenizde sizi geleceğe bağlayan minik üyeler var mı?",
            ],
            
            QuestionCategory.SALARY: [
                f"{connector}, yaşam standartlarınız için ayırdığınız tahmini pay ne kadardır?",
                "Konforlu bir gelecek için aylık harcama vizyonunuzu nasıl tanımlarsınız?",
            ],
            
            QuestionCategory.HOBBIES: [
                f"Ruhunuzu en çok hangi uğraşlar dinlendiriyor {name}?",
                "Hangi tutkular sizi hayata daha sıkı bağlar?",
            ],
            
            QuestionCategory.PETS: [
                "Sadık bir dostla (evcil hayvan) paylaşılan bir hayatın huzuru sizin için ne ifade eder?",
                "Evinizde patili bir dostun enerjisi olsun ister miydiniz?",
            ],
            
            QuestionCategory.BUDGET: [
                f"Hayallerinizi somutlaştırmak için ayırdığınız o kıymetli maddi kaynak yaklaşık ne kadardır {name}?",
                f"Konforunuzun finansal sınırlarını nasıl çizersiniz {name}?",
            ],
            
            QuestionCategory.LOCATION: [
                f"Gözlerinizi her sabah hangi şehrin ışığına açmak istersiniz {name}?",
                "Tercih ettiğiniz iklim veya sahil kasabası hayaliniz var mı?",
            ],
            
            QuestionCategory.PROPERTY_TYPE: [
                "Gökyüzüne yakın bir rezidans mı, yoksa toprağa dokunan bir bahçeli yaşam mı size hitap ediyor?",
                f"Sizin ruhunuza hangi mimari doku iyi geliyor {name}?",
            ],
            
            QuestionCategory.ROOMS: [
                "Sessizliği dinleyebileceğiniz veya sevdiklerinizi ağırlayabileceğiniz genişliği nasıl hayal edersiniz?",
                "Yaşam alanınızın ferahlığı kaç odada hayat bulmalı?",
            ],
            
            QuestionCategory.FAMILY_SIZE: [
                f"Bu vizyonu kaç kişilik bir toplulukla paylaşmayı düşünüyorsunuz {name}?",
                "Ferahlığın tanımı sizin kalabalığınız için nedir?",
            ],
        }
        
        question_options = questions.get(category)
        
        if isinstance(question_options, list):
            return random.choice(question_options)
        elif question_options:
            return question_options
        else:
            return f"{category.value} hakkında bilgi verir misiniz?"
