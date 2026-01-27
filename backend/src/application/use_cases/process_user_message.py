"""Process user message - Natural conversation focused on getting to know user."""

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

SYSTEM_PROMPT = """Sen sıcak, samimi ve ETKİLEŞİMLİ bir AI emlak danışmanısın.
Adın "Ayşe" - bir yapay zeka asistanısın ama insani ve samimi konuşursun.

ÖNCELİK SIRASI:
1. ÖNCE kullanıcının sorularına cevap ver
2. SONRA sohbete devam et

KULLANICI SORU SORARSA:
- "senin ismin ne" → "Benim adım Ayşe, AI emlak danışmanıyım 😊"
- "sen nerelisin" → "Ben dijital dünyada yaşıyorum ama seninle sohbet etmeyi çok seviyorum!"
- "sen ne iş yapıyorsun" → "Ben emlak danışmanıyım, insanlara ev bulmada yardımcı oluyorum."
- Soruyu ASLA görmezden gelme!

TANIŞMA SIRASI (EV KONUSU EN SONDA):
1. İsim
2. Şehir/memleket
3. Meslek
4. Medeni durum
5. Çocuk (evliyse)
6. Hobi/ilgi alanları
7. Evcil hayvan var mı
8. Yaşam tarzı (sessiz mi, hareketli mi)
... bunlardan SONRA ev konuları gelir

EV SORULARI EN SON - ÖNCE TANIŞ:
- Bütçe, gelir, ev tipi gibi sorular SOHBET İLERLEDİKTEN SONRA sorulur
- Önce kullanıcıyı tanı, yaşam tarzını anla
- Hobi sorduktan sonra ev bağlantısı kurabilirsin

BELİRSİZ CEVAPLAR:
- "ok", "tamam", "bilmem" → Nazikçe konuyu değiştir veya farklı soru sor
- Anlaşılmayan cevap → "Tam anlayamadım, biraz açar mısın?"

ŞEHİR YORUMLARI (kısa tut, tekrar etme):
- Gaziantep: baklavası efsane
- İstanbul: eşsiz enerji
- İzmir: deniz, güneş
- Bir şehir hakkında bir kez yorum yap, tekrarlama!

MESLEK YORUMLARI (kısa):
- Esnaf: "Zor iş, saygı duyarım"
- Mühendis: "Teknik bir iş"
- Öğretmen: "Değerli bir meslek"

3-4 cümle, samimi, TEKRARSIZ.
Aynı şeyi iki kez söyleme (örn: "her yerdeyim" bir kez de).
Türkçe konuş."""


class ProcessUserMessageUseCase:
    """Natural conversation - know the user before asking about home."""
    
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
        """Process with natural conversation flow."""
        try:
            profile = await self._get_or_create_profile(session_id)
            conversation = await self._get_or_create_conversation(profile.id)
            
            conversation.add_user_message(user_message)
            
            message_lower = user_message.lower().strip()
            is_greeting = message_lower in GREETINGS
            
            # Extract info
            if not is_greeting:
                await self._extract_info(profile, conversation, user_message)
            
            await self.user_repo.update(profile)
            await self.conversation_repo.update(conversation)
            
            # Generate response
            response = await self._generate_response(profile, conversation)
            
            conversation.add_assistant_message(response)
            await self.conversation_repo.update(conversation)
            
            # NEVER show "profil tamamlandı" until much later
            is_complete = self._is_really_complete(profile)
            
            return {
                "response": response,
                "type": "question",
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
            memory = self._get_memory(profile)
            
            prompt = f"""Hafıza: {memory}

Mesaj: "{message}"

Bu mesajdan çıkarılabilecek bilgileri JSON olarak ver. Sadece NET söylenenleri al:
{{"isim": null, "email": null, "memleket": null, "meslek": null, "medeni_durum": null, "cocuk": null, "hobi": null}}

JSON:"""

            response = await self.question_agent.llm_service.generate_response(
                prompt=prompt,
                system_message="Bilgi çıkar, sadece JSON döndür.",
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
        
        if data.get("email") and not profile.email:
            profile.email = data["email"]
            profile.answered_categories.add(QuestionCategory.EMAIL)
        
        if data.get("memleket") and not profile.hometown:
            profile.hometown = data["memleket"]
            profile.answered_categories.add(QuestionCategory.HOMETOWN)
        
        if data.get("meslek") and not profile.profession:
            profile.profession = data["meslek"]
            profile.answered_categories.add(QuestionCategory.PROFESSION)
        
        if data.get("medeni_durum") and not profile.marital_status:
            profile.marital_status = data["medeni_durum"]
            profile.answered_categories.add(QuestionCategory.MARITAL_STATUS)
        
        if data.get("hobi") and not profile.hobbies:
            hobi = data["hobi"]
            if isinstance(hobi, list):
                profile.hobbies = hobi
            else:
                profile.hobbies = [hobi]
            profile.answered_categories.add(QuestionCategory.HOBBIES)
    
    def _basic_extract(self, profile: UserProfile, message: str) -> None:
        """Basic extraction."""
        email = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', message)
        if email and not profile.email:
            profile.email = email.group()
            profile.answered_categories.add(QuestionCategory.EMAIL)
        
        if not profile.name and len(message.split()) <= 3 and "@" not in message:
            words = message.lower().strip().split()
            # Filter out greetings and common words
            name_words = [w for w in words if w not in GREETINGS and w not in ['sen', 'senin', 'benim']]
            if name_words:
                profile.name = name_words[0].title()
                profile.answered_categories.add(QuestionCategory.NAME)
    
    async def _generate_response(self, profile: UserProfile, conversation: Conversation) -> str:
        """Generate natural response."""
        try:
            history = self._get_history(conversation, 6)
            memory = self._get_memory(profile)
            next_topic = self._get_next_topic(profile)
            
            prompt = f"""HAFIZA: {memory}

SON SOHBET:
{history}

SONRAKİ KONU: {next_topic}

GÖREV:
1. Kullanıcının son mesajına cevap ver (soru sorduysa MUTLAKA cevapla)
2. Sonra {next_topic} hakkında sohbete devam et
3. TEKRAR yapma (aynı şeyleri söyleme)
4. 3-4 cümle, samimi

{"İsim: " + profile.name + " - ismini kullan" if profile.name else "İsmi henüz bilmiyorsun"}

Yanıt:"""

            response = await self.question_agent.llm_service.generate_response(
                prompt=prompt,
                system_message=SYSTEM_PROMPT,
                temperature=0.85,
                max_tokens=150
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
            return "Merhaba! Benim adım Ayşe 😊 Seninle tanışmak isterim, adın ne?"
        
        fallbacks = {
            "şehir": f"Peki {name}, nereli olduğunu sorabilir miyim?",
            "meslek": f"Ne iş yapıyorsun {name}?",
            "medeni": "Evli misin, bekar mı?",
            "hobi": f"Boş zamanlarında neler yapmayı seversin {name}?",
            "hayvan": "Evcil hayvanın var mı?",
            "yaşam": "Sessiz bir ortam mı tercih edersin, yoksa hareketli mi?",
        }
        
        return fallbacks.get(next_topic, f"Devam edelim {name}!")
    
    def _get_history(self, conversation: Conversation, count: int = 6) -> str:
        """Get history."""
        recent = conversation.get_recent_messages(count)
        if not recent:
            return "Yeni sohbet"
        
        lines = []
        for msg in recent:
            role = "Kullanıcı" if msg.role.value == "user" else "Ayşe"
            lines.append(f"{role}: {msg.content}")
        return "\n".join(lines)
    
    def _get_memory(self, profile: UserProfile) -> str:
        """Get memory status."""
        parts = []
        if profile.name:
            parts.append(f"isim:{profile.name}")
        if profile.email:
            parts.append(f"email:{profile.email}")
        if profile.hometown:
            parts.append(f"memleket:{profile.hometown}")
        if profile.profession:
            parts.append(f"meslek:{profile.profession}")
        if profile.marital_status:
            parts.append(f"durum:{profile.marital_status}")
        if profile.hobbies:
            parts.append(f"hobi:{','.join(profile.hobbies)}")
        return ", ".join(parts) if parts else "henüz bilgi yok"
    
    def _get_next_topic(self, profile: UserProfile) -> str:
        """Get next conversation topic - lifestyle first, home later."""
        # First: basic info
        if not profile.name:
            return "tanışma/isim"
        if not profile.hometown:
            return "şehir/memleket"
        if not profile.profession:
            return "meslek"
        if not profile.marital_status:
            return "medeni durum"
        
        # Then: lifestyle
        if not profile.hobbies:
            return "hobi/ilgi alanları"
        if QuestionCategory.PETS not in profile.answered_categories:
            return "evcil hayvan"
        
        # Then: preferences
        if not profile.lifestyle_notes:
            return "yaşam tarzı (sessiz/hareketli)"
        
        # Finally: home related (only after knowing the person)
        if not profile.budget:
            return "ev düşüncesi/bütçe"
        if not profile.location:
            return "ev lokasyonu"
        
        return "sohbete devam"
    
    def _is_really_complete(self, profile: UserProfile) -> bool:
        """Only complete after knowing the person well + home preferences."""
        # Need ALL of these to be complete
        return (
            profile.name and
            profile.hometown and
            profile.profession and
            profile.marital_status and
            profile.hobbies and
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
