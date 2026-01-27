"""Process user message - Strict question order, no unnecessary info."""

from typing import Optional
from uuid import UUID
import re
import json

from application.agents import QuestionAgent, ValidationAgent, AnalysisAgent
from domain.entities import UserProfile, Conversation
from domain.repositories import IUserRepository, IConversationRepository
from domain.enums import QuestionCategory
from infrastructure.config import get_logger


GREETINGS = {'merhaba', 'selam', 'selamlar', 'mrb', 'slm', 'hey', 'hi', 'sa', 'merhabalar', 'naber'}

SYSTEM_PROMPT = """Sen samimi ve doğal bir AI emlak danışmanı Ayşe'sin.

SOHBET TARZI:
- Doğal, akıcı, samimi
- 2-4 cümle arası (bağlama göre)
- Katı sıra yok, sohbet bağlamına göre sor
- Kullanıcıyı zorlamıyorsun, cevap vermezse geç

TOPLANACAK BİLGİLER (esnek sıra):
- İsim, şehir, meslek
- Medeni durum, çocuk
- Hobi, evcil hayvan  
- Ev için: bütçe, şehir, oda sayısı

DOĞAL GEÇİŞLER:
- Kullanıcı bir şey söylerse ona uygun soru sor
- Mesela "evliyim" derse → çocuk sor
- "Spor yapıyorum" derse → buna yorum yap, sonra devam et
- Kullanıcı geçiştirirse → farklı konuya geç

ZORLAMAK YOK:
- "ok", "bilmem", "geçelim" gibi cevaplara → başka konuya geç
- Aynı soruyu iki kez sorma

EMOJİ:
- Bazen, her mesajda değil
- Farklı emojiler

"sen" sorusuna kısa cevap ver, sonra sohbete devam et.
Türkçe, samimi, doğal."""


class ProcessUserMessageUseCase:
    """Strict question order with no skipping."""
    
    # Question order - strictly followed
    QUESTION_ORDER = [
        ("name", "isim", None),
        ("hometown", "memleket", "Nereli olduğunu sorabilir miyim?"),
        ("profession", "meslek", "Ne iş yapıyorsun?"),
        ("marital", "medeni durum", "Evli misin, bekar mı?"),
        ("children", "çocuk", "Çocuğunuz var mı?"),
        ("hobbies", "hobi", "Boş zamanlarında ne yapmayı seversin?"),
        ("pets", "evcil hayvan", "Evcil hayvanın var mı?"),
        ("budget", "bütçe", "Ev için düşündüğün bir bütçe var mı?"),
        ("target_city", "ev şehri", "Hangi şehirde ev arıyorsun?"),
        ("rooms", "oda sayısı", "Kaç odalı bir ev düşünüyorsun?"),
    ]
    
    def __init__(
        self,
        user_repository: IUserRepository,
        conversation_repository: IConversationRepository,
        question_agent: QuestionAgent,
        validation_agent: ValidationAgent,
        analysis_agent: AnalysisAgent,
    ):
        self.user_repo = user_repository
        self.conversation_repo = conversation_repository
        self.question_agent = question_agent
        self.validation_agent = validation_agent
        self.analysis_agent = analysis_agent
        self.logger = get_logger(self.__class__.__name__)
    
    async def execute(self, session_id: str, user_message: str) -> dict:
        """Process with strict question order."""
        try:
            profile = await self._get_or_create_profile(session_id)
            conversation = await self._get_or_create_conversation(profile.id)
            
            conversation.add_user_message(user_message)
            
            # Extract info
            await self._extract_info(profile, conversation, user_message)
            
            await self.user_repo.update(profile)
            await self.conversation_repo.update(conversation)
            
            # Get next question in order
            current_step = self._get_current_step(profile)
            self.logger.info(f"Current step: {current_step}")
            
            # Generate response
            response = await self._generate_response(profile, conversation, current_step)
            
            conversation.add_assistant_message(response)
            await self.conversation_repo.update(conversation)
            
            is_complete = current_step == "complete"
            
            return {
                "response": response,
                "type": "analysis" if is_complete else "question",
                "is_complete": is_complete,
                "category": current_step,
            }
            
        except Exception as e:
            self.logger.error(f"Error: {e}", exc_info=True)
            return {
                "response": "Pardon, bir aksaklık oldu. Devam edelim mi?",
                "type": "error",
                "is_complete": False,
            }
    
    def _get_current_step(self, profile: UserProfile) -> str:
        """Get suggested topics based on what's missing - FLEXIBLE."""
        missing = []
        
        if not profile.name:
            missing.append("isim")
        if not profile.hometown:
            missing.append("memleket")
        if not profile.profession:
            missing.append("meslek")
        if not profile.marital_status:
            missing.append("medeni durum")
        if profile.marital_status and 'evli' in profile.marital_status.lower():
            if profile.has_children is None:
                missing.append("çocuk")
        if not profile.hobbies:
            missing.append("hobi")
        if QuestionCategory.PETS not in profile.answered_categories:
            missing.append("evcil hayvan")
        if not profile.budget:
            missing.append("bütçe")
        if not profile.location:
            missing.append("ev şehri")
        if not profile.property_preferences:
            missing.append("oda sayısı")
        
        if not missing:
            return "complete"
        
        # Return all missing as suggestion (LLM decides)
        return ", ".join(missing[:3])  # Max 3 suggestions
    
    async def _extract_info(self, profile: UserProfile, conversation: Conversation, message: str) -> None:
        """Extract info from message."""
        msg = message.strip()
        msg_lower = msg.lower()
        
        # Remove "sen" questions for extraction
        clean_msg = msg_lower.replace(" sen", "").replace("sen ", "").strip()
        
        # Get current step to know what we're expecting
        current = self._get_current_step(profile)
        
        if current == "name" and msg_lower not in GREETINGS:
            # Extract name
            words = [w for w in clean_msg.split() if w not in GREETINGS and w not in ['benim', 'adım', 'ben']]
            if words:
                profile.name = words[0].title()
                profile.answered_categories.add(QuestionCategory.NAME)
        
        elif current == "hometown":
            # Extract city
            cities = ['istanbul', 'ankara', 'izmir', 'gaziantep', 'antalya', 'bursa', 'adana', 
                     'konya', 'samsun', 'trabzon', 'amasya', 'mersin', 'kayseri', 'diyarbakır']
            for city in cities:
                if city in clean_msg:
                    profile.hometown = city.title()
                    profile.answered_categories.add(QuestionCategory.HOMETOWN)
                    break
            if not profile.hometown and len(clean_msg) < 30:
                profile.hometown = clean_msg.title()
                profile.answered_categories.add(QuestionCategory.HOMETOWN)
        
        elif current == "profession":
            profile.profession = clean_msg
            profile.answered_categories.add(QuestionCategory.PROFESSION)
        
        elif current == "marital":
            if 'evli' in clean_msg:
                profile.marital_status = "evli"
            elif 'bekar' in clean_msg:
                profile.marital_status = "bekar"
            else:
                profile.marital_status = clean_msg
            profile.answered_categories.add(QuestionCategory.MARITAL_STATUS)
        
        elif current == "children":
            if 'yok' in clean_msg or 'hayır' in clean_msg:
                profile.has_children = False
                profile.family_size = 0
            else:
                profile.has_children = True
                nums = re.findall(r'\d+', clean_msg)
                profile.family_size = int(nums[0]) if nums else 1
            profile.answered_categories.add(QuestionCategory.CHILDREN)
        
        elif current == "hobbies":
            profile.hobbies = [clean_msg]
            profile.answered_categories.add(QuestionCategory.HOBBIES)
        
        elif current == "pets":
            profile.answered_categories.add(QuestionCategory.PETS)
        
        elif current == "budget":
            nums = re.findall(r'(\d+)', clean_msg.replace('.', '').replace(',', ''))
            if nums:
                from domain.value_objects import Budget
                amt = int(nums[0])
                if amt < 100:  # Probably millions
                    amt = amt * 1000000
                elif amt < 10000:  # Probably thousands
                    amt = amt * 1000
                profile.budget = Budget(min_amount=int(amt * 0.8), max_amount=int(amt * 1.2))
                profile.answered_categories.add(QuestionCategory.BUDGET)
        
        elif current == "target_city":
            from domain.value_objects import Location
            profile.location = Location(city=clean_msg.title(), country="Turkey")
            profile.answered_categories.add(QuestionCategory.LOCATION)
        
        elif current == "rooms":
            from domain.value_objects import PropertyPreferences
            from domain.enums import PropertyType
            nums = re.findall(r'\d+', clean_msg)
            rooms = int(nums[0]) if nums else 3
            profile.property_preferences = PropertyPreferences(
                property_type=PropertyType.APARTMENT,
                min_rooms=rooms
            )
            profile.answered_categories.add(QuestionCategory.ROOMS)
    
    async def _generate_response(self, profile: UserProfile, conversation: Conversation, next_step: str) -> str:
        """Generate response with next question."""
        try:
            history = self._get_history(conversation, 4)
            
            # Check if user asked "sen" question
            last_msg = ""
            recent = conversation.get_recent_messages(1)
            if recent:
                last_msg = recent[0].content.lower()
            has_sen_question = "sen" in last_msg
            
            # Step-specific prompts
            step_hints = {
                "name": "tanışma, isim sor",
                "hometown": "nereli olduğunu sor",
                "profession": "ne iş yaptığını sor",
                "marital": "evli mi bekar mı sor",
                "children": "çocuğu var mı sor",
                "hobbies": "hobisini sor",
                "pets": "evcil hayvanı var mı sor",
                "budget": "ev için bütçesini sor",
                "target_city": "hangi şehirde ev aradığını sor",
                "rooms": "kaç oda istediğini sor",
                "complete": "tamamlandı, teşekkür et",
            }
            
            prompt = f"""SOHBET:
{history}

SONRAKİ SORU: {step_hints.get(next_step, next_step)}
{"KULLANICI 'SEN' DİYE SORDU - KISA CEVAP VER: 'Ben Ayşe!' veya 'Ben AI asistanım' SONRA kendi sorunu sor" if has_sen_question else ""}
İSİM: {profile.name or 'bilinmiyor'}

GÖREV:
1. Önceki cevaba kısa yorum (1 cümle)
2. {step_hints.get(next_step, 'sohbete devam')}
3. MAX 2-3 cümle
4. Gereksiz bilgi verme (sorulmadan "yapay zekayım" deme)

Yanıt:"""

            response = await self.question_agent.llm_service.generate_response(
                prompt=prompt,
                system_message=SYSTEM_PROMPT,
                temperature=0.8,
                max_tokens=100
            )
            
            result = response.strip()
            
            # Prevent asking for name when we have it
            if profile.name and any(p in result.lower() for p in ["ismin", "adın ne"]):
                return self._fallback(profile, next_step)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Generate error: {e}")
            return self._fallback(profile, next_step)
    
    def _fallback(self, profile: UserProfile, step: str) -> str:
        """Simple fallback questions."""
        name = profile.name or ""
        
        fallbacks = {
            "name": "Merhaba! Ben Ayşe. Adın ne?",
            "hometown": f"{name}, nereli olduğunu sorabilir miyim?",
            "profession": f"Ne iş yapıyorsun {name}?",
            "marital": "Evli misin, bekar mı?",
            "children": "Çocuğunuz var mı?",
            "hobbies": f"Boş zamanlarında ne yapmayı seversin {name}?",
            "pets": "Evcil hayvanın var mı?",
            "budget": f"{name}, ev için düşündüğün bir bütçe var mı?",
            "target_city": "Hangi şehirde ev arıyorsun?",
            "rooms": "Kaç odalı bir ev düşünüyorsun?",
            "complete": f"Harika {name}! Tüm bilgileri aldım, şimdi sana uygun evler önerebilirim.",
        }
        
        return fallbacks.get(step, f"Devam edelim {name}!")
    
    def _get_history(self, conversation: Conversation, count: int = 4) -> str:
        """Get history."""
        recent = conversation.get_recent_messages(count)
        if not recent:
            return "Yeni sohbet"
        
        lines = []
        for msg in recent:
            role = "K" if msg.role.value == "user" else "A"
            lines.append(f"{role}: {msg.content}")
        return "\n".join(lines)
    
    async def _get_or_create_profile(self, session_id: str) -> UserProfile:
        try:
            p = await self.user_repo.get_by_session_id(session_id)
            if not p:
                p = UserProfile(session_id=session_id)
                p = await self.user_repo.create(p)
            return p
        except:
            return UserProfile(session_id=session_id)
    
    async def _get_or_create_conversation(self, user_id: UUID) -> Conversation:
        try:
            c = await self.conversation_repo.get_by_user_profile_id(user_id)
            if not c:
                c = Conversation(user_profile_id=user_id)
                c = await self.conversation_repo.create(c)
            return c
        except:
            return Conversation(user_profile_id=user_id)
