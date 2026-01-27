"""Process user message - Short, natural, human-like conversation."""

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

ÖNCELİK SIRASI:
1. ÖNCE kullanıcının sorularına cevap ver (eğer soru sorduysa)
2. SONRA kendi sorunu sor

KULLANICI SORU SORARSA ("sen" ile biten sorular):
- "gaziantep sen" = "sen nerelisin?" demek → ÖNCE cevap ver: "Ben dijital bir asistanım, her yerdeyim 😊"
- "bilgisayar mühendisiyim sen" = "sen ne iş yapıyorsun?" → "Ben AI emlak danışmanıyım!"
- Kullanıcının sorusunu ASLA görmezden gelme!

BELİRSİZ CEVAPLAR (ok, tamam, hmm, evet, hayır):
- "ok" veya "tamam" → Bu bir onay, devam et ama nazik ol: "Anladım! Peki şunu sorabilir miyim..."
- Anlamsız cevap → Kibarca tekrar sor: "Tam anlayamadım, biraz açar mısın?"

3-4 CÜMLE, SAMİMİ, ETKİLEŞİMLİ:
- Şehir söylenirse o şehrin özelliğinden bahset
- Meslek söylenirse yorum yap
- Kullanıcı soru sorarsa MUTLAKA cevapla

ŞEHİR YORUMLARI:
- Gaziantep: baklavası, kebabı efsane
- İstanbul: şehrin enerjisi, Boğaz
- İzmir: denizi, havası
- Ankara: başkent
- Antalya: denizi, turizm

İYİ ÖRNEKLER:
"Gaziantep mi? Oranın baklavası efsane! 😊 Sen nerelisin dedin, ben dijital bir asistanım, her yerdeyim. Peki ne iş yapıyorsun İlayda?"
"Yazılımcı ha, zor iş! Ben de bir nevi yazılımım aslında 😄 Peki evli misin, bekar mı?"
"Hmm, tam anlayamadım. Evli misin yoksa bekar mı diye sormuştum?"

KÖTÜ ÖRNEK (yapma):
Kullanıcı: "gaziantep sen"
Bot: "Gaziantep mi? Harika! Peki mesleğin ne?" ← SEN SORUSUNU GÖRMEZLİKTEN GELDİ!

Türkçe, samimi, etkileşimli, 3-4 cümle."""


class ProcessUserMessageUseCase:
    """Short, natural conversation for real estate."""
    
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
        """Process with short natural responses."""
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
            
            # Generate short response
            response = await self._generate_response(profile, conversation)
            
            conversation.add_assistant_message(response)
            await self.conversation_repo.update(conversation)
            
            return {
                "response": response,
                "type": "question",
                "is_complete": self._is_complete(profile),
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
{{"isim": null, "email": null, "memleket": null, "meslek": null, "medeni_durum": null, "cocuk": null, "gelir": null}}

JSON:"""

            response = await self.question_agent.llm_service.generate_response(
                prompt=prompt,
                system_message="Bilgi çıkar, sadece JSON döndür.",
                temperature=0.1,
                max_tokens=150
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
        
        if data.get("gelir") and not profile.estimated_salary:
            profile.estimated_salary = data["gelir"]
            profile.answered_categories.add(QuestionCategory.SALARY)
    
    def _basic_extract(self, profile: UserProfile, message: str) -> None:
        """Basic extraction."""
        email = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', message)
        if email and not profile.email:
            profile.email = email.group()
            profile.answered_categories.add(QuestionCategory.EMAIL)
        
        if not profile.name and len(message.split()) <= 2 and "@" not in message:
            if message.lower().strip() not in GREETINGS:
                profile.name = message.strip().title()
                profile.answered_categories.add(QuestionCategory.NAME)
    
    async def _generate_response(self, profile: UserProfile, conversation: Conversation) -> str:
        """Generate SHORT natural response."""
        try:
            history = self._get_history(conversation, 4)
            memory = self._get_memory(profile)
            missing = self._get_missing(profile)
            
            prompt = f"""Bilinen: {memory}
Eksik: {missing}

Sohbet:
{history}

Görev: Kısa ve doğal cevap ver, sonraki bilgiyi al.

KURALLAR:
- MAX 1-2 CÜMLE
- Övme, drama yok
- Doğal ol
- {"İsim: " + profile.name if profile.name else "İsmi sor"}

Yanıt:"""

            response = await self.question_agent.llm_service.generate_response(
                prompt=prompt,
                system_message=SYSTEM_PROMPT,
                temperature=0.8,
                max_tokens=150  # Rich but balanced
            )
            
            result = response.strip()
            
            # Loop protection
            if profile.name and any(p in result.lower() for p in ["isminiz", "hitap", "adınız"]):
                return self._fallback(profile, missing)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Generate error: {e}")
            return self._fallback(profile, self._get_missing(profile))
    
    def _fallback(self, profile: UserProfile, missing: list) -> str:
        """Short fallback responses."""
        name = profile.name or ""
        
        if not name:
            return "Merhaba! Adın ne?"
        
        if not missing:
            return f"Süper {name}! Şimdi sana uygun evlere bakalım."
        
        next_field = missing[0]
        
        responses = {
            "email": f"Tamam {name}, mail adresini alabilir miyim?",
            "memleket": f"Nereli olduğunu sorabilir miyim {name}?",
            "meslek": f"Ne iş yapıyorsun {name}?",
            "medeni_durum": "Evli misin, bekar mı?",
            "gelir": "Bütçe olarak nasıl düşünüyorsun?",
        }
        
        return responses.get(next_field, f"Devam edelim {name}!")
    
    def _get_history(self, conversation: Conversation, count: int = 4) -> str:
        """Get history."""
        recent = conversation.get_recent_messages(count)
        if not recent:
            return "Yeni sohbet"
        
        lines = []
        for msg in recent:
            role = "K" if msg.role.value == "user" else "S"
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
        return ", ".join(parts) if parts else "yok"
    
    def _get_missing(self, profile: UserProfile) -> list:
        """Get missing fields."""
        missing = []
        if not profile.name:
            missing.append("isim")
        if not profile.email:
            missing.append("email")
        if not profile.hometown:
            missing.append("memleket")
        if not profile.profession:
            missing.append("meslek")
        if not profile.marital_status:
            missing.append("medeni_durum")
        if not profile.estimated_salary:
            missing.append("gelir")
        return missing
    
    def _is_complete(self, profile: UserProfile) -> bool:
        """Check completion."""
        return (
            profile.name and
            profile.email and
            profile.hometown and
            profile.profession
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
