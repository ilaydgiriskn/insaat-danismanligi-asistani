"""Process user message - Natural conversation with proper data persistence."""

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
- Kullanıcıyı zorlamıyorsun

BİLGİ TOPLAMA (esnek, doğal):
- İsim, şehir, meslek
- Medeni durum, çocuk
- Hobi, yaşam tarzı
- Sonra ev konuları (ama "ev arayışı" deme, yumuşak ol)

EV KONUSU İÇİN YUMUŞAK İFADELER:
- "Ev arayışındasınız" DEMİYORSUN
- Bunun yerine: "İleride taşınmayı düşünür müsün?", "Farklı bir yere yerleşmek ister misin?"
- Ya da: "Yaşam alanı olarak ne düşünüyorsun?"

ZORLAMAK YOK:
- Cevap vermezse geç
- Aynı soruyu iki kez sorma

EMOJİ: Bazen, her mesajda değil, farklı emojiler

"sen" sorusuna kısa cevap ver.
Türkçe, samimi, doğal."""


class ProcessUserMessageUseCase:
    """Natural conversation with proper data persistence."""
    
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
        """Process message naturally."""
        try:
            profile = await self._get_or_create_profile(session_id)
            conversation = await self._get_or_create_conversation(profile.id)
            
            conversation.add_user_message(user_message)
            
            # Extract ALL possible info from message
            self._extract_all_info(profile, user_message)
            
            await self.user_repo.update(profile)
            await self.conversation_repo.update(conversation)
            
            # Log what we have
            self.logger.info(f"Profile: name={profile.name}, hometown={profile.hometown}, profession={profile.profession}, marital={profile.marital_status}")
            
            # Get missing info
            missing = self._get_missing_info(profile)
            
            # Generate response
            response = await self._generate_response(profile, conversation, missing)
            
            conversation.add_assistant_message(response)
            await self.conversation_repo.update(conversation)
            
            is_complete = not missing
            
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
    
    def _extract_all_info(self, profile: UserProfile, message: str) -> None:
        """Extract ALL possible info from message - not step-dependent."""
        msg = message.strip()
        msg_lower = msg.lower()
        
        # Clean message
        clean = msg_lower.replace(" sen", "").replace("sen ", "").strip()
        
        # Skip if greeting only
        if clean in GREETINGS:
            return
        
        # Extract NAME (if we don't have it and message is short)
        if not profile.name and len(clean.split()) <= 3:
            words = [w for w in clean.split() if w not in GREETINGS and w not in ['benim', 'adım', 'ben', 'evet', 'hayır']]
            if words and len(words[0]) > 1:
                profile.name = words[0].title()
                profile.answered_categories.add(QuestionCategory.NAME)
                self.logger.info(f"Extracted name: {profile.name}")
                return  # Name was the answer
        
        # Extract CITY (common Turkish cities)
        cities = ['istanbul', 'ankara', 'izmir', 'gaziantep', 'antalya', 'bursa', 'adana', 
                 'konya', 'samsun', 'trabzon', 'amasya', 'mersin', 'kayseri', 'diyarbakır',
                 'eskişehir', 'denizli', 'malatya', 'erzurum', 'van', 'mardin', 'muğla']
        for city in cities:
            if city in clean:
                if not profile.hometown:
                    profile.hometown = city.title()
                    profile.answered_categories.add(QuestionCategory.HOMETOWN)
                    self.logger.info(f"Extracted hometown: {profile.hometown}")
                elif not profile.location:
                    # Might be target city for home
                    from domain.value_objects import Location
                    profile.location = Location(city=city.title(), country="Turkey")
                    profile.answered_categories.add(QuestionCategory.LOCATION)
                    self.logger.info(f"Extracted target city: {city}")
                break
        
        # Extract PROFESSION (common professions)
        professions = ['doktor', 'mühendis', 'öğretmen', 'avukat', 'hemşire', 'esnaf', 
                      'mimar', 'muhasebeci', 'yazılımcı', 'polis', 'asker', 'memur',
                      'bankacı', 'gazeteci', 'şoför', 'aşçı', 'garson']
        for prof in professions:
            if prof in clean and not profile.profession:
                profile.profession = prof.title()
                profile.answered_categories.add(QuestionCategory.PROFESSION)
                self.logger.info(f"Extracted profession: {profile.profession}")
                break
        
        # Also check for profession patterns
        if not profile.profession:
            prof_patterns = [
                r'(\w+)\s*(olarak çalışıyorum|işi yapıyorum)',
                r'ben\s+(\w+)',
            ]
            for pattern in prof_patterns:
                match = re.search(pattern, clean)
                if match:
                    potential = match.group(1)
                    if potential not in GREETINGS and len(potential) > 2:
                        if potential.endswith('ım') or potential.endswith('im') or potential.endswith('um'):
                            # Remove suffix
                            potential = potential[:-2] if len(potential) > 4 else potential
                        profile.profession = potential.title()
                        profile.answered_categories.add(QuestionCategory.PROFESSION)
                        self.logger.info(f"Extracted profession from pattern: {profile.profession}")
                        break
        
        # Extract MARITAL STATUS
        if not profile.marital_status:
            if 'evliyim' in clean or 'evli' in clean:
                profile.marital_status = "evli"
                profile.answered_categories.add(QuestionCategory.MARITAL_STATUS)
                self.logger.info("Extracted: evli")
            elif 'bekarım' in clean or 'bekar' in clean:
                profile.marital_status = "bekar"
                profile.answered_categories.add(QuestionCategory.MARITAL_STATUS)
                self.logger.info("Extracted: bekar")
        
        # Extract CHILDREN info
        if profile.has_children is None:
            if 'çocuğum yok' in clean or 'çocuk yok' in clean:
                profile.has_children = False
                profile.family_size = 0
                profile.answered_categories.add(QuestionCategory.CHILDREN)
            elif 'çocuğum var' in clean or 'çocuk var' in clean or 'tane' in clean:
                profile.has_children = True
                nums = re.findall(r'\d+', clean)
                profile.family_size = int(nums[0]) if nums else 1
                profile.answered_categories.add(QuestionCategory.CHILDREN)
                self.logger.info(f"Extracted children: {profile.family_size}")
        
        # Extract HOBBIES
        hobbies = ['spor', 'yüzme', 'koşu', 'futbol', 'basketbol', 'tenis', 'golf',
                  'okumak', 'kitap', 'müzik', 'sinema', 'tiyatro', 'yemek', 'seyahat',
                  'fotoğraf', 'resim', 'dans', 'yoga', 'pilates']
        for hobby in hobbies:
            if hobby in clean and not profile.hobbies:
                profile.hobbies = [hobby]
                profile.answered_categories.add(QuestionCategory.HOBBIES)
                self.logger.info(f"Extracted hobby: {hobby}")
                break
        
        # Extract EMAIL
        email = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', msg)
        if email and not profile.email:
            profile.email = email.group()
            profile.answered_categories.add(QuestionCategory.EMAIL)
    
    def _get_missing_info(self, profile: UserProfile) -> list:
        """Get list of missing info."""
        missing = []
        
        if not profile.name:
            missing.append("isim")
        if not profile.hometown:
            missing.append("memleket")
        if not profile.profession:
            missing.append("meslek")
        if not profile.marital_status:
            missing.append("medeni durum")
        
        # If married, need children info
        if profile.marital_status == "evli" and profile.has_children is None:
            missing.append("çocuk")
        
        if not profile.hobbies:
            missing.append("hobi")
        
        # Home-related (later in conversation)
        basic_done = profile.name and profile.hometown and profile.profession
        if basic_done:
            if not profile.budget:
                missing.append("yaşam tercihi")  # Softer than "bütçe"
            if not profile.location:
                missing.append("taşınma düşüncesi")  # Softer than "ev şehri"
        
        return missing
    
    async def _generate_response(self, profile: UserProfile, conversation: Conversation, missing: list) -> str:
        """Generate natural response - fully LLM-driven."""
        try:
            history = self._get_history(conversation, 6)
            memory = self._get_memory(profile)
            
            topic = missing[0] if missing else "sohbete devam"
            
            prompt = f"""BİLİNEN BİLGİLER: {memory}

SON SOHBET:
{history}

EKSİK BİLGİLER: {', '.join(missing[:5]) if missing else 'Tüm temel bilgiler alındı'}

GÖREV:
Kullanıcının son mesajına samimi ve doğal bir yanıt ver. 
Sonra eksik bilgilerden birini öğrenmek için soru sor.

ÖNEMLİ KURALLAR:
- 3-5 cümle yaz (zengin ama uzatma)
- Önceki mesaja bağlan
- Şehir/meslek söylediyse yorumla
- Zaten bilinen şeyleri tekrar sorma
- "Ev arayışındasınız" gibi direkt ifadeler kullanma
- Doğal geçişler yap

{"İSİM BİLİNİYOR: " + profile.name + " - kullan" if profile.name else "İSMİ ÖĞRENMELİSİN"}
{"MESLEK BİLİNİYOR: " + profile.profession + " - tekrar sorma" if profile.profession else ""}

Sadece yanıt metnini yaz (sabit kalıplar kullanma, her mesajı yeni üret):"""

            response = await self.question_agent.llm_service.generate_response(
                prompt=prompt,
                system_message=SYSTEM_PROMPT,
                temperature=0.9,  # More creative
                max_tokens=200  # Longer responses
            )
            
            result = response.strip()
            
            # Remove any prefix
            if result.startswith("A:") or result.startswith("Ayşe:"):
                result = result.split(":", 1)[1].strip()
            
            return result
            
        except Exception as e:
            self.logger.error(f"Generate error: {e}")
            # Minimal fallback only for errors
            if not profile.name:
                return "Merhaba! Ben Ayşe, AI emlak danışmanınızım. Seninle tanışmak isterim, adın ne?"
            return f"Devam edelim {profile.name}! Seninle sohbet etmek güzel."
    
    def _fallback(self, profile: UserProfile, topic: str) -> str:
        """Minimal fallback - only for critical errors."""
        name = profile.name or ""
        if not name:
            return "Merhaba! Ben Ayşe. Adın ne?"
        return f"Devam edelim {name}!"
    
    def _get_history(self, conversation: Conversation, count: int = 4) -> str:
        """Get history - clean format."""
        recent = conversation.get_recent_messages(count)
        if not recent:
            return "Yeni sohbet"
        
        lines = []
        for msg in recent:
            role = "Kullanıcı" if msg.role.value == "user" else "Ayşe"
            lines.append(f"{role}: {msg.content}")
        return "\n".join(lines)
    
    def _get_memory(self, profile: UserProfile) -> str:
        """Get memory."""
        parts = []
        if profile.name:
            parts.append(f"İsim: {profile.name}")
        if profile.hometown:
            parts.append(f"Şehir: {profile.hometown}")
        if profile.profession:
            parts.append(f"Meslek: {profile.profession}")
        if profile.marital_status:
            parts.append(f"Durum: {profile.marital_status}")
        if profile.has_children is not None:
            parts.append(f"Çocuk: {'var' if profile.has_children else 'yok'}")
        if profile.hobbies:
            parts.append(f"Hobi: {profile.hobbies[0]}")
        return ", ".join(parts) if parts else "Henüz bilgi yok"
    
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
