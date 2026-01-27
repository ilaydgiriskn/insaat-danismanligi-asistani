"""Process user message - Focused conversation for home needs discovery."""

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

SYSTEM_PROMPT = """Sen sıcak, samimi bir AI emlak danışmanısın. Adın Ayşe.

EMOJİ KURALLARI:
- Her mesajda emoji KULLANMA
- 3-4 mesajda bir emoji yeterli
- Hep aynı emoji olmasın (😊 😄 🏠 👍 gibi değiş)

SOHBET ODAĞI:
Asıl amacın: kullanıcının EV İHTİYACINI anlamak
- Tanışma önemli ama KISA tut
- Hobiye veya evcil hayvana çok takılma (1 cümle yorum yeter)
- Evli diyorsa → HEMEN çocuk sor (ev boyutu için önemli)
- Sonra ev konularına geç (bütçe, oda sayısı, konum)

SORU SIRASI:
1. İsim
2. Şehir/memleket (kısa yorum)
3. Meslek (kısa yorum)
4. Medeni durum
5. Çocuk sayısı (evliyse - ÖNEMLİ, ev boyutu için)
6. Hobi (kısa, 1 cümle yorum yeter)
7. Evcil hayvan (var/yok yeter, detaya girme)
8. → EV KONULARINA GEÇ: bütçe, hangi şehirde ev, kaç oda, ev tipi

KISA TUT:
- Her konuya 1-2 cümle yorum yeter
- Evcil hayvan varsa "güzel" de geç, isim vs. sorma
- Amaca odaklan: ev bulmak

UZUNLUK: 2-3 cümle max. Samimi ama öz.

KULLANICI SORU SORARSA:
- "senin" = sana soru soruyor, cevap ver
- Ama kısa cevap ver ve konuya dön

Türkçe, samimi, ODAKLI, 2-3 cümle."""


class ProcessUserMessageUseCase:
    """Focused conversation for home needs discovery."""
    
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
        """Process with focused conversation."""
        try:
            profile = await self._get_or_create_profile(session_id)
            conversation = await self._get_or_create_conversation(profile.id)
            
            conversation.add_user_message(user_message)
            
            message_lower = user_message.lower().strip()
            is_greeting = message_lower in GREETINGS
            
            if not is_greeting:
                await self._extract_info(profile, conversation, user_message)
            
            await self.user_repo.update(profile)
            await self.conversation_repo.update(conversation)
            
            response = await self._generate_response(profile, conversation)
            
            conversation.add_assistant_message(response)
            await self.conversation_repo.update(conversation)
            
            is_complete = self._is_complete(profile)
            
            return {
                "response": response,
                "type": "analysis" if is_complete else "question",
                "is_complete": is_complete,
                "category": None,
            }
            
        except Exception as e:
            self.logger.error(f"Error: {e}", exc_info=True)
            return {
                "response": "Pardon, bir aksaklık oldu. Devam edelim mi?",
                "type": "error",
                "is_complete": False,
            }
    
    async def _extract_info(self, profile: UserProfile, conversation: Conversation, message: str) -> None:
        """Extract info from message."""
        try:
            prompt = f"""Mesaj: "{message}"

JSON olarak çıkar (sadece net bilgiler):
{{"isim": null, "memleket": null, "meslek": null, "medeni_durum": null, "cocuk_sayisi": null, "hobi": null, "evcil_hayvan": null, "butce": null, "hedef_sehir": null, "oda_sayisi": null}}

JSON:"""

            response = await self.question_agent.llm_service.generate_response(
                prompt=prompt,
                system_message="Bilgi çıkar, JSON döndür.",
                temperature=0.1,
                max_tokens=100
            )
            
            try:
                content = response.strip()
                if "```" in content:
                    content = content.split("```")[1].replace("json", "").strip()
                data = json.loads(content)
                self._apply_data(profile, data)
            except:
                self._basic_extract(profile, message)
                
        except Exception as e:
            self.logger.error(f"Extract error: {e}")
            self._basic_extract(profile, message)
    
    def _apply_data(self, profile: UserProfile, data: dict) -> None:
        """Apply extracted data."""
        if data.get("isim") and not profile.name:
            profile.name = data["isim"]
            profile.answered_categories.add(QuestionCategory.NAME)
        
        if data.get("memleket") and not profile.hometown:
            profile.hometown = data["memleket"]
            profile.answered_categories.add(QuestionCategory.HOMETOWN)
        
        if data.get("meslek") and not profile.profession:
            profile.profession = data["meslek"]
            profile.answered_categories.add(QuestionCategory.PROFESSION)
        
        if data.get("medeni_durum") and not profile.marital_status:
            profile.marital_status = data["medeni_durum"]
            profile.answered_categories.add(QuestionCategory.MARITAL_STATUS)
        
        if data.get("cocuk_sayisi") is not None:
            profile.has_children = data["cocuk_sayisi"] > 0
            profile.family_size = data["cocuk_sayisi"]
            profile.answered_categories.add(QuestionCategory.CHILDREN)
        
        if data.get("hobi"):
            profile.hobbies = [data["hobi"]] if isinstance(data["hobi"], str) else data["hobi"]
            profile.answered_categories.add(QuestionCategory.HOBBIES)
        
        if data.get("evcil_hayvan"):
            profile.answered_categories.add(QuestionCategory.PETS)
        
        if data.get("butce") and not profile.budget:
            from domain.value_objects import Budget
            try:
                nums = re.findall(r'\d+', str(data["butce"]).replace('.', '').replace(',', ''))
                if nums:
                    amt = int(nums[0]) * 1000 if int(nums[0]) < 10000 else int(nums[0])
                    profile.budget = Budget(min_amount=int(amt * 0.8), max_amount=int(amt * 1.2))
                    profile.answered_categories.add(QuestionCategory.BUDGET)
            except:
                pass
        
        if data.get("hedef_sehir") and not profile.location:
            from domain.value_objects import Location
            profile.location = Location(city=data["hedef_sehir"], country="Turkey")
            profile.answered_categories.add(QuestionCategory.LOCATION)
        
        if data.get("oda_sayisi") and not profile.property_preferences:
            from domain.value_objects import PropertyPreferences
            from domain.enums import PropertyType
            profile.property_preferences = PropertyPreferences(
                property_type=PropertyType.APARTMENT,
                min_rooms=data["oda_sayisi"]
            )
            profile.answered_categories.add(QuestionCategory.ROOMS)
    
    def _basic_extract(self, profile: UserProfile, message: str) -> None:
        """Basic extraction."""
        msg_lower = message.lower()
        
        # Email
        email = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', message)
        if email and not profile.email:
            profile.email = email.group()
            profile.answered_categories.add(QuestionCategory.EMAIL)
        
        # Marital status
        if 'evli' in msg_lower and not profile.marital_status:
            profile.marital_status = "evli"
            profile.answered_categories.add(QuestionCategory.MARITAL_STATUS)
        elif 'bekar' in msg_lower and not profile.marital_status:
            profile.marital_status = "bekar"
            profile.answered_categories.add(QuestionCategory.MARITAL_STATUS)
        
        # Name
        if not profile.name and len(message.split()) <= 4 and "@" not in message:
            words = [w for w in message.lower().split() if w not in GREETINGS and w not in ['sen', 'senin', 'benim', 'adım']]
            if words and len(words[0]) > 1:
                profile.name = words[0].title()
                profile.answered_categories.add(QuestionCategory.NAME)
    
    async def _generate_response(self, profile: UserProfile, conversation: Conversation) -> str:
        """Generate focused response."""
        try:
            history = self._get_history(conversation, 4)
            memory = self._get_memory(profile)
            next_topic = self._get_next_topic(profile)
            
            prompt = f"""HAFIZA: {memory}

SOHBET:
{history}

SONRAKİ SORU: {next_topic}

GÖREV:
1. Önceki cevaba KISA tepki (1 cümle)
2. {next_topic} hakkında sor
3. MAX 2-3 cümle
4. Her mesajda emoji KULLANMA

Yanıt:"""

            response = await self.question_agent.llm_service.generate_response(
                prompt=prompt,
                system_message=SYSTEM_PROMPT,
                temperature=0.8,
                max_tokens=120
            )
            
            result = response.strip()
            
            # Loop protection
            if profile.name and "ismin" in result.lower():
                return self._fallback(profile, next_topic)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Generate error: {e}")
            return self._fallback(profile, self._get_next_topic(profile))
    
    def _fallback(self, profile: UserProfile, next_topic: str) -> str:
        """Fallback responses."""
        name = profile.name or ""
        
        if not name:
            return "Merhaba! Ben Ayşe. Seninle tanışmak isterim, adın ne?"
        
        fallbacks = {
            "şehir": f"{name}, nereli olduğunu sorabilir miyim?",
            "meslek": f"Ne iş yapıyorsun {name}?",
            "medeni": "Evli misin, bekar mı?",
            "çocuk": "Çocuğunuz var mı, kaç tane?",
            "hobi": "Kısaca, boş zamanlarında ne yaparsın?",
            "hayvan": "Evcil hayvanın var mı?",
            "bütçe": f"{name}, ev için düşündüğün bir bütçe var mı?",
            "şehir_ev": "Hangi şehirde ev arıyorsun?",
            "oda": "Kaç odalı bir ev düşünüyorsun?",
            "tip": "Daire mi, müstakil ev mi tercih edersin?",
        }
        
        return fallbacks.get(next_topic, f"Devam edelim {name}!")
    
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
    
    def _get_memory(self, profile: UserProfile) -> str:
        """Get memory."""
        parts = []
        if profile.name:
            parts.append(f"isim:{profile.name}")
        if profile.hometown:
            parts.append(f"şehir:{profile.hometown}")
        if profile.profession:
            parts.append(f"meslek:{profile.profession}")
        if profile.marital_status:
            parts.append(f"durum:{profile.marital_status}")
        if profile.has_children is not None:
            parts.append(f"çocuk:{'var' if profile.has_children else 'yok'}")
        if profile.hobbies:
            parts.append("hobi:var")
        if QuestionCategory.PETS in profile.answered_categories:
            parts.append("hayvan:soruldu")
        if profile.budget:
            parts.append(f"bütçe:{profile.budget.max_amount}")
        if profile.location:
            parts.append(f"hedef:{profile.location.city}")
        return ", ".join(parts) if parts else "yok"
    
    def _get_next_topic(self, profile: UserProfile) -> str:
        """Get next topic - focused on home needs."""
        if not profile.name:
            return "isim"
        if not profile.hometown:
            return "şehir"
        if not profile.profession:
            return "meslek"
        if not profile.marital_status:
            return "medeni"
        
        # If married, ask about children IMMEDIATELY
        if profile.marital_status and 'evli' in profile.marital_status.lower():
            if profile.has_children is None:
                return "çocuk"
        
        # Quick lifestyle check
        if not profile.hobbies:
            return "hobi"
        if QuestionCategory.PETS not in profile.answered_categories:
            return "hayvan"
        
        # HOME QUESTIONS - the real goal
        if not profile.budget:
            return "bütçe"
        if not profile.location:
            return "şehir_ev"
        if not profile.property_preferences:
            return "oda"
        
        return "tamamlama"
    
    def _is_complete(self, profile: UserProfile) -> bool:
        """Check if ready for recommendations."""
        return (
            profile.name and
            profile.budget and
            profile.location and
            profile.property_preferences
        )
    
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
