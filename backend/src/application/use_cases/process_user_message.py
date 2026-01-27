"""Process user message - Fully LLM-driven human-like conversation."""

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

SYSTEM_PROMPT = """Sen insan gibi sohbet eden, bağlamı güçlü, hafızalı bir AI emlak danışmanısın.
Kullanıcıyla konuşurken asla "soru soruyorum" hissi yaratmazsın.
Amacın: kullanıcıyı tanımak ve gerekli bilgileri sohbet içinde, doğal geçişlerle toplamak.

SOHBET ÜRETİM KURALLARI:
- Cümleleri SABİT metinlerle kurma, her mesajı kendin üret
- Aynı anda yalnızca 1 bilgi hedefle
- Sorular asla şu şekilde olmasın: "İsminiz nedir?", "Mesleğiniz?"
- Sorular her zaman sohbet cümlesi içinde gelsin

DOĞAL GEÇİŞ MANTIĞI:
- Önceki cevaba referans ver
- Küçük bir sohbet cümlesi içer
- Karşılıklı konuşma hissi yarat

HASSAS BİLGİ (MAAŞ/GELİR):
- Asla net rakam zorlanmaz
- Aralık veya rahatlık seviyesi üzerinden sor
- Gerekçesini sohbet içinde ver

SOHBET TONU:
- Samimi, akıcı, hafif gülümseten
- Asla robotik değil
- Emoji az ve doğru yerde, her mesajda değil

Kullanıcı fark etmeden bilgi verir. Sen farkında olarak hepsini hafızaya alırsın."""


class ProcessUserMessageUseCase:
    """Fully LLM-driven natural conversation for real estate."""
    
    # Fields to collect (tracked internally)
    REQUIRED_FIELDS = [
        "isim", "email", "memleket", "meslek", "medeni_durum",
        "cocuk_sayisi", "gelir", "hobiler", "evcil_hayvan",
        "butce", "hedef_sehir", "ev_tipi"
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
        """Process with fully LLM-driven conversation."""
        try:
            # Get profile and conversation
            profile = await self._get_or_create_profile(session_id)
            conversation = await self._get_or_create_conversation(profile.id)
            
            # Add user message
            conversation.add_user_message(user_message)
            
            message_lower = user_message.lower().strip()
            is_greeting = message_lower in GREETINGS or any(message_lower.startswith(g + " ") for g in GREETINGS)
            
            # Extract info from message using LLM
            if not is_greeting:
                await self._extract_info(profile, conversation, user_message)
            
            # Save
            await self.user_repo.update(profile)
            await self.conversation_repo.update(conversation)
            
            # Generate response
            response = await self._generate_response(profile, conversation)
            
            # Save response
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
                "response": "Pardon, biraz karıştırdım. Nerede kalmıştık? 😊",
                "type": "error",
                "is_complete": False,
            }
    
    async def _extract_info(self, profile: UserProfile, conversation: Conversation, message: str) -> None:
        """Extract info using LLM."""
        try:
            history = self._get_history(conversation, 4)
            current_memory = self._get_memory_status(profile)
            
            prompt = f"""HAFIZA DURUMU:
{current_memory}

SON SOHBET:
{history}

KULLANICININ SON MESAJI: "{message}"

GÖREV: Bu mesajdan çıkarılabilecek bilgileri JSON olarak çıkar.
Sadece NET söylenen bilgileri al, tahmin yapma.
Zaten hafızada olan bilgileri tekrar çıkarma.

JSON:
{{
    "isim": "isim veya null",
    "email": "email veya null",
    "memleket": "şehir veya null",
    "meslek": "meslek veya null",
    "medeni_durum": "evli/bekar veya null",
    "cocuk_var_mi": true/false veya null,
    "cocuk_sayisi": sayı veya null,
    "gelir": "gelir aralığı/açıklama veya null",
    "hobiler": ["hobi"] veya null,
    "evcil_hayvan": "hayvan türü veya null",
    "butce_min": sayı veya null,
    "butce_max": sayı veya null,
    "hedef_sehir": "şehir veya null",
    "ev_tipi": "daire/villa/müstakil veya null"
}}

Sadece JSON döndür:"""

            response = await self.question_agent.llm_service.generate_response(
                prompt=prompt,
                system_message="Bilgi çıkarma uzmanısın. Sadece net bilgileri çıkar, tahmin yapma.",
                temperature=0.1,
                max_tokens=250
            )
            
            # Parse and apply
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
        """Apply extracted data to profile."""
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
        
        if data.get("cocuk_var_mi") is not None and profile.has_children is None:
            profile.has_children = data["cocuk_var_mi"]
            if data.get("cocuk_sayisi"):
                profile.family_size = data["cocuk_sayisi"]
            profile.answered_categories.add(QuestionCategory.CHILDREN)
        
        if data.get("gelir") and not profile.estimated_salary:
            profile.estimated_salary = data["gelir"]
            profile.answered_categories.add(QuestionCategory.SALARY)
        
        if data.get("hobiler") and not profile.hobbies:
            profile.hobbies = data["hobiler"]
            profile.answered_categories.add(QuestionCategory.HOBBIES)
        
        if data.get("evcil_hayvan"):
            profile.answered_categories.add(QuestionCategory.PETS)
            if not profile.lifestyle_notes:
                profile.lifestyle_notes = f"Evcil hayvan: {data['evcil_hayvan']}"
        
        if data.get("butce_min") and not profile.budget:
            from domain.value_objects import Budget
            min_amt = data["butce_min"]
            max_amt = data.get("butce_max") or int(min_amt * 1.2)
            profile.budget = Budget(min_amount=min_amt, max_amount=max_amt)
            profile.answered_categories.add(QuestionCategory.BUDGET)
        
        if data.get("hedef_sehir") and not profile.location:
            from domain.value_objects import Location
            profile.location = Location(city=data["hedef_sehir"], country="Turkey")
            profile.answered_categories.add(QuestionCategory.LOCATION)
        
        if data.get("ev_tipi") and not profile.property_preferences:
            from domain.value_objects import PropertyPreferences
            from domain.enums import PropertyType
            
            t = data["ev_tipi"].lower()
            if "villa" in t:
                ptype = PropertyType.VILLA
            elif "müstakil" in t:
                ptype = PropertyType.DETACHED_HOUSE
            else:
                ptype = PropertyType.APARTMENT
            
            profile.property_preferences = PropertyPreferences(property_type=ptype)
            profile.answered_categories.add(QuestionCategory.PROPERTY_TYPE)
    
    def _basic_extract(self, profile: UserProfile, message: str) -> None:
        """Basic extraction fallback."""
        # Email
        email = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', message)
        if email and not profile.email:
            profile.email = email.group()
            profile.answered_categories.add(QuestionCategory.EMAIL)
        
        # If no name and message is short, might be name
        if not profile.name and len(message.split()) <= 3 and "@" not in message:
            if message.lower().strip() not in GREETINGS:
                profile.name = message.strip().title()
                profile.answered_categories.add(QuestionCategory.NAME)
    
    async def _generate_response(self, profile: UserProfile, conversation: Conversation) -> str:
        """Generate fully LLM-driven response."""
        try:
            history = self._get_history(conversation, 6)
            memory = self._get_memory_status(profile)
            missing = self._get_missing_fields(profile)
            
            prompt = f"""HAFIZADAKI BİLGİLER:
{memory}

EKSİK BİLGİLER: {missing}

SON SOHBET:
{history}

GÖREV:
Kullanıcının son mesajına doğal bir tepki ver ve sohbeti devam ettir.
Eksik bilgilerden BİRİNİ doğal bir şekilde, sohbet içinde öğrenmeye çalış.

KURALLAR:
1. Sabit metin kullanma, her mesajı kendin yaz
2. "İsminiz nedir?", "Mesleğiniz?" gibi direkt sorma
3. Önceki cevaba referans ver, bağlam kur
4. 1-2 cümle max
5. Her mesajda emoji kullanma
6. Hafızadaki bilgileri ASLA tekrar sorma
7. İsim biliniyorsa hitap için kullan

{"İSİM BİLİNİYOR: " + profile.name + " - hitap et ama isim sorma!" if profile.name else "İSİM BİLİNMİYOR - önce tanışmayı başlat, ismi öğren"}

SONRAKİ HEDEF: {missing[0] if missing else "Tüm bilgiler tamam"}

Sadece yanıt metnini yaz (SABİT KALIPLER KULLANMA):"""

            response = await self.question_agent.llm_service.generate_response(
                prompt=prompt,
                system_message=SYSTEM_PROMPT,
                temperature=0.85,
                max_tokens=100
            )
            
            result = response.strip()
            
            # Loop protection
            if profile.name:
                bad_phrases = ["isminiz", "hitap edebilirim", "adınız", "nasıl hitap", "ismini öğren"]
                if any(p in result.lower() for p in bad_phrases):
                    return self._safe_continue(profile, missing)
            
            return result
            
        except Exception as e:
            self.logger.error(f"Generate error: {e}")
            return self._safe_continue(profile, self._get_missing_fields(profile))
    
    def _safe_continue(self, profile: UserProfile, missing: list) -> str:
        """Safe continuation without loops."""
        name = profile.name or ""
        
        if not name:
            return "Merhaba! Ben AI emlak danışmanınızım. Seninle tanışmak isterim 😊"
        
        if not missing:
            return f"Harika {name}! Tüm bilgileri aldım, şimdi size en uygun seçenekleri hazırlayabilirim."
        
        next_field = missing[0]
        
        safe_responses = {
            "email": f"{name}, iletişim için mail adresini alabilir miyim?",
            "memleket": f"Peki {name}, memleketini merak ettim açıkçası.",
            "meslek": f"{name}, bu arada ne iş yapıyorsun merak ettim.",
            "medeni_durum": "Evli misin, bekar mı?",
            "gelir": "Bütçe konusunda rahat mı hareket ediyoruz yoksa biraz dikkatli mi gitmeli?",
            "hobiler": f"{name}, boş zamanlarında neler yapmayı seversin?",
            "butce": "Ev için düşündüğün bir bütçe aralığı var mı?",
            "hedef_sehir": "Hangi şehirde ev bakıyoruz?",
            "ev_tipi": "Daire mi düşünüyorsun yoksa müstakil bir şeyler mi?",
        }
        
        return safe_responses.get(next_field, f"Devam edelim {name}, biraz daha sohbet edelim.")
    
    def _get_history(self, conversation: Conversation, count: int = 6) -> str:
        """Get conversation history."""
        recent = conversation.get_recent_messages(count)
        if not recent:
            return "Yeni sohbet başladı"
        
        lines = []
        for msg in recent:
            role = "Kullanıcı" if msg.role.value == "user" else "Sen"
            lines.append(f"{role}: {msg.content}")
        return "\n".join(lines)
    
    def _get_memory_status(self, profile: UserProfile) -> str:
        """Get current memory status."""
        parts = []
        
        if profile.name:
            parts.append(f"✓ isim: {profile.name}")
        if profile.email:
            parts.append(f"✓ email: {profile.email}")
        if profile.hometown:
            parts.append(f"✓ memleket: {profile.hometown}")
        if profile.profession:
            parts.append(f"✓ meslek: {profile.profession}")
        if profile.marital_status:
            parts.append(f"✓ medeni_durum: {profile.marital_status}")
        if profile.has_children is not None:
            parts.append(f"✓ çocuk: {'var' if profile.has_children else 'yok'}")
        if profile.estimated_salary:
            parts.append(f"✓ gelir: {profile.estimated_salary}")
        if profile.hobbies:
            parts.append(f"✓ hobiler: {', '.join(profile.hobbies)}")
        if QuestionCategory.PETS in profile.answered_categories:
            parts.append("✓ evcil_hayvan: soruldu")
        if profile.budget:
            parts.append(f"✓ bütçe: {profile.budget.min_amount:,}-{profile.budget.max_amount:,} TL")
        if profile.location:
            parts.append(f"✓ hedef_şehir: {profile.location.city}")
        if profile.property_preferences:
            parts.append(f"✓ ev_tipi: {profile.property_preferences.property_type.value}")
        
        return "\n".join(parts) if parts else "Henüz bilgi yok"
    
    def _get_missing_fields(self, profile: UserProfile) -> list:
        """Get list of missing fields."""
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
        if profile.has_children is None:
            missing.append("çocuk")
        if not profile.estimated_salary:
            missing.append("gelir")
        if not profile.hobbies:
            missing.append("hobiler")
        if QuestionCategory.PETS not in profile.answered_categories:
            missing.append("evcil_hayvan")
        if not profile.budget:
            missing.append("butce")
        if not profile.location:
            missing.append("hedef_sehir")
        if not profile.property_preferences:
            missing.append("ev_tipi")
        
        return missing
    
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
