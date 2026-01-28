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
        missing_info: list[str] = None
    ) -> dict:
        """Select next question using LLM based on user profile and history."""
        try:
            self._log_execution("Generating discovery question via LLM")
            
            # Get context
            history = self._get_history_text(conversation)
            system_msg = self.prompt_manager.get_system_message("question")
            
            # Prepare detailed profile state
            profile_summary = self._get_profile_summary(user_profile)
            missing_str = ", ".join(missing_info) if missing_info else "Bilinmiyor"
            
            user_msg = f"""MEVCUT BİLGİLER:
{profile_summary}

EKSİK BİLGİLER: {missing_str}

KONUŞMA GEÇMİŞİ (Sondan başa doğru):
{history}

GÖREV: Yukarıdaki kurallara göre doğal bir sonraki soruyu veya kapanış cümlesini seç."""

            # Use structured response for the requested JSON format
            result = await self.llm_service.generate_structured_response(
                prompt=user_msg,
                system_message=system_msg,
                response_format={
                    "question": "string or null",
                    "category": "string or null",
                    "message": "string or null"
                }
            )
            
            return result
            
        except Exception as e:
            self._log_error(e)
            # True fallback to deterministic method if LLM fails
            unanswered = user_profile.get_unanswered_categories()
            return self._fallback_question_selection(user_profile, unanswered)

    def _get_history_text(self, conversation: Conversation, count: int = 5) -> str:
        """Get recent history as text - chronological."""
        messages = conversation.messages[-count:]
        history_parts = []
        for msg in messages:
            role = "Kullanıcı" if msg.role == "user" else "Asistan"
            history_parts.append(f"{role}: {msg.content}")
        return "\n".join(history_parts)

    def _get_profile_summary(self, profile: UserProfile) -> str:
        """Get brief summary of what we know."""
        parts = []
        if profile.name: parts.append(f"- İsim: {profile.name}")
        if profile.surname: parts.append(f"- Soyisim: {profile.surname}")
        if profile.profession: parts.append(f"- Meslek: {profile.profession}")
        if profile.current_city: parts.append(f"- Yaşadığı Yer: {profile.current_city}")
        if profile.email: parts.append(f"- Email: {profile.email}")
        if profile.estimated_salary: parts.append(f"- Gelir: {profile.estimated_salary}")
        return "\n".join(parts) if parts else "Hiçbir bilgi yok."
    
    def _fallback_question_selection(
        self,
        user_profile: UserProfile,
        unanswered: set[QuestionCategory]
    ) -> dict:
        """Deterministic question selection - no LLM, predictable order."""
        
        # Priority order (New requirements)
        priority = [
            QuestionCategory.NAME,
            QuestionCategory.SURNAME,
            QuestionCategory.PROFESSION,
            QuestionCategory.ESTIMATED_SALARY,
            QuestionCategory.EMAIL,
            QuestionCategory.HOMETOWN, # Living place/current city
            QuestionCategory.LOCATION,
            QuestionCategory.ROOMS,
            QuestionCategory.MARITAL_STATUS,
            QuestionCategory.HOBBIES,
            QuestionCategory.PHONE_NUMBER,
        ]
        
        for category in priority:
            if category in unanswered:
                question = self._get_natural_question(user_profile, category)
                return {
                    "question": question,
                    "category": category.value,
                    "message": "Anladım.",
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
            QuestionCategory.NAME: "Memnun oldum! Sizi hangi isimle tanıyabilirim?",
            QuestionCategory.SURNAME: f"Memnun oldum {name}! Soyadınızı da öğrenebilir miyim?",
            
            QuestionCategory.EMAIL: [
                f"Harika {name}. Sizinle iletişimde kalabilmemiz için e-posta adresinizi paylaşır mısınız?",
                f"Teşekkürler {name}. Mail adresinizi de alabilir miyim acaba?",
            ],
            
            QuestionCategory.PHONE_NUMBER: [
                "Size hızlıca ulaşabileceğimiz bir telefon numaranız var mı?",
                "Sizinle irtibatta kalmak adına telefon numaranızı da rica etsem paylaşır mısınız?",
            ],
            
            QuestionCategory.HOMETOWN: [
                f"Anladım {name}. Peki, şu an hangi şehir ve semtte oturuyorsunuz?",
                f"{name}, şu an yaşadığınız yer neresi acaba (şehir/ilçe)?",
            ],
            
            QuestionCategory.PROFESSION: [
                "Çok güzel. Ne ile meşgulsünüz, mesleğiniz nedir acaba?",
                "Anladım. Hangi işle meşgul olduğunuzu da öğrenebilir miyim?",
            ],
            
            QuestionCategory.MARITAL_STATUS: [
                "Sizin için en uygun evi bakarken, medeni durumunuzu da sorsam sorun olur mu? (Evli/Bekar vb.)",
                "Yaşam alanınızı kiminle paylaşacaksınız, aile durumu nedir acaba?",
            ],
            
            QuestionCategory.ESTIMATED_SALARY: [
                "Bütçenize en uygun seçenekleri sunabilmem için aylık ortalama gelirinizi paylaşır mısınız?",
                "Size daha doğru önerilerde bulunmak adına, yaklaşık aylık kazancınızı da öğrenebilir miyim?",
            ],
            
            QuestionCategory.HOBBIES: [
                f"Harika {name}. Evde zaman geçirirken yapmaktan en çok keyif aldığınız hobileriniz nelerdir?",
                f"Sizin için evde olmazsa olmaz bir hobi alanı gerekir mi, nelerle ilgilenirsiniz?",
            ],
            
            QuestionCategory.BUDGET: [
                "Ev için ayırmayı düşündüğünüz bütçe aralığı yaklaşık nedir?",
                "Finansal olarak hangi bütçe aralığında seçeneklere bakmak istersiniz?",
            ],
            
            QuestionCategory.LOCATION: [
                "Ev almak istediğiniz, hayalinizdeki o özel semt veya bölge neresi?",
                "Hangi lokasyonlarda kendinizi daha mutlu ve huzurlu hissedersiniz?",
            ],
            
            QuestionCategory.ROOMS: [
                "Kaç oda, kaç salon bir ev sizin için ideal olur?",
                "Evde kaç odalı bir plana ihtiyacınız var?",
            ],
        }
        
        question_options = questions.get(category)
        
        if isinstance(question_options, list):
            return random.choice(question_options)
        elif question_options:
            return question_options
        else:
            return f"{category.value} hakkında bilgi verir misiniz?"
