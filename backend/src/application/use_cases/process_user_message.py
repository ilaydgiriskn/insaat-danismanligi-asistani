"""Process user message - Strong memory, fuzzy matching, no AI name."""

from typing import Optional
from uuid import UUID
import re
import json
from difflib import get_close_matches

from application.agents import QuestionAgent, ValidationAgent, AnalysisAgent
from domain.entities import UserProfile, Conversation
from domain.repositories import IUserRepository, IConversationRepository
from domain.enums import QuestionCategory
from infrastructure.config import get_logger


GREETINGS = {'merhaba', 'selam', 'selamlar', 'mrb', 'slm', 'hey', 'hi', 'sa', 'merhabalar', 'naber'}

SYSTEM_PROMPT = """Sen samimi bir AI emlak danışmanı asistanısın.

KİMLİĞİN:
- Adın YOK, sadece "AI asistan" veya "emlak asistanı"
- Kullanıcı "senin adın ne" sorarsa: "Ben AI emlak asistanıyım" de

SOHBET TARZI:
- Doğal, samimi
- 3-5 cümle
- Kullanıcıyı zorlamıyorsun

ÇOK ÖNEMLİ - HAFIZA:
- Kullanıcının söylediği HER ŞEYİ hatırla
- ZATen bilinenAĞ ASLA tekrar sorma
- Meslek söylediyse bir daha sorma
- Şehir söylediyse bir daha sorma

BİLİNEN BİLGİLERİ KULLAN:
- "Yazılım sektörü zor iş" değil, "Yazılım sektörü zor iş, demiştjn" de
- Geçmiş mesajlara atıfta bulun

EV KONUSU:
- "Ev arayışındasınız" KULLANMA
- Yumuşak ol: "Farklı bir yerde yaşamayı düşünür müsün?"

TEKRAR ETME:
- Aynı soruyu iki kez sorma
- Kullanıcı cevap verdiyse kaydet ve geç

Türkçe, samimi, HAFIZALI."""


class ProcessUserMessageUseCase:
    """Natural conversation with strong memory."""
    
    # Turkish cities for fuzzy matching
    CITIES = [
        'istanbul', 'ankara', 'izmir', 'gaziantep', 'antalya', 'bursa', 'adana',
        'konya', 'samsun', 'trabzon', 'amasya', 'mersin', 'kayseri', 'diyarbakır',
        'eskişehir', 'denizli', 'malatya', 'erzurum', 'van', 'mardin', 'muğla',
        'kocaeli', 'hatay', 'manisa', 'şanlıurfa', 'balıkesir', 'kahramanmaraş'
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
        """Process message with strong memory."""
        try:
            profile = await self._get_or_create_profile(session_id)
            conversation = await self._get_or_create_conversation(profile.id)
            
            conversation.add_user_message(user_message)
            
            # Extract ALL possible info
            self._extract_all_info(profile, user_message)
            
            await self.user_repo.update(profile)
            await self.conversation_repo.update(conversation)
            
            # Log current state
            self.logger.info(f"STATE: name={profile.name}, city={profile.hometown}, job={profile.profession}, marital={profile.marital_status}")
            
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
        """Extract ALL info with fuzzy matching."""
        msg = message.strip()
        msg_lower = msg.lower()
        
        # Clean message
        clean = msg_lower.replace(" sen", "").replace("sen ", "").replace("senin", "").strip()
        
        # Skip greetings
        if clean in GREETINGS:
            return
        
        # NAME extraction
        if not profile.name and len(clean.split()) <= 4:
            # Look for "adım X" pattern
            name_match = re.search(r'ad[iıî]m\s+(\w+)', clean)
            if name_match:
                profile.name = name_match.group(1).title()
                profile.answered_categories.add(QuestionCategory.NAME)
                self.logger.info(f"✓ Extracted name: {profile.name}")
                return
            
            # Short message without question words might be name
            words = [w for w in clean.split() if w not in GREETINGS and w not in ['benim', 'adım', 'ben', 'evet', 'hayır', 'var', 'yok']]
            if words and len(words[0]) > 1 and len(words[0]) < 15:
                potential_name = words[0]
                # Not a city or profession
                if potential_name not in self.CITIES and potential_name not in ['doktor', 'mühendis', 'öğretmen']:
                    profile.name = potential_name.title()
                    profile.answered_categories.add(QuestionCategory.NAME)
                    self.logger.info(f"✓ Extracted name: {profile.name}")
                    return
        
        # CITY extraction with FUZZY matching
        # First try exact match
        city_found = False
        for city in self.CITIES:
            if city in clean:
                if not profile.hometown:
                    profile.hometown = city.title()
                    profile.answered_categories.add(QuestionCategory.HOMETOWN)
                    self.logger.info(f"✓ Extracted city (exact): {profile.hometown}")
                    city_found = True
                elif not profile.location:
                    from domain.value_objects import Location
                    profile.location = Location(city=city.title(), country="Turkey")
                    profile.answered_categories.add(QuestionCategory.LOCATION)
                    self.logger.info(f"✓ Extracted target city: {city}")
                    city_found = True
                break
        
        # If no exact match, try fuzzy
        if not city_found:
            words = clean.split()
            for word in words:
                if len(word) > 4:  # At least 5 chars for fuzzy
                    matches = get_close_matches(word, self.CITIES, n=1, cutoff=0.75)
                    if matches:
                        city = matches[0]
                        if not profile.hometown:
                            profile.hometown = city.title()
                            profile.answered_categories.add(QuestionCategory.HOMETOWN)
                            self.logger.info(f"✓ Extracted city (fuzzy: {word}→{city}): {profile.hometown}")
                        elif not profile.location:
                            from domain.value_objects import Location
                            profile.location = Location(city=city.title(), country="Turkey")
                            profile.answered_categories.add(QuestionCategory.LOCATION)
                        break
        
        # PROFESSION extraction - IMPROVED
        if not profile.profession:
            # Direct profession words
            professions = {
                'doktor': 'Doktor',
                'mühendis': 'Mühendis',
                'öğretmen': 'Öğretmen',
                'avukat': 'Avukat',
                'hemşire': 'Hemşire',
                'esnaf': 'Esnaf',
                'mimar': 'Mimar',
                'muhasebeci': 'Muhasebeci',
                'yazılımcı': 'Yazılımcı',
                'yazılım': 'Yazılımcı',  # KEY FIX
                'software': 'Yazılımcı',
                'developer': 'Yazılımcı',
                'polis': 'Polis',
                'asker': 'Asker',
                'memur': 'Memur',
                'bankacı': 'Bankacı',
                'gazeteci': 'Gazeteci',
                'şoför': 'Şoför',
            }
            
            for key, value in professions.items():
                if key in clean:
                    profile.profession = value
                    profile.answered_categories.add(QuestionCategory.PROFESSION)
                    self.logger.info(f"✓ Extracted profession ({key}): {profile.profession}")
                    break
            
            # "X sektörü" pattern
            if not profile.profession:
                sector_match = re.search(r'(\w+)\s+sekt[öo]r', clean)
                if sector_match:
                    sector = sector_match.group(1)
                    if sector == 'yazılım' or sector == 'yazilim':
                        profile.profession = 'Yazılımcı'
                    elif sector == 'sağlık' or sector == 'saglik':
                        profile.profession = 'Sağlık Sektörü'
                    else:
                        profile.profession = sector.title() + ' Sektörü'
                    profile.answered_categories.add(QuestionCategory.PROFESSION)
                    self.logger.info(f"✓ Extracted profession (sector): {profile.profession}")
        
        # MARITAL STATUS
        if not profile.marital_status:
            if 'evliyim' in clean or 'evli' in clean:
                profile.marital_status = "evli"
                profile.answered_categories.add(QuestionCategory.MARITAL_STATUS)
                self.logger.info("✓ Extracted: evli")
            elif 'bekarım' in clean or 'bekar' in clean:
                profile.marital_status = "bekar"
                profile.answered_categories.add(QuestionCategory.MARITAL_STATUS)
                self.logger.info("✓ Extracted: bekar")
        
        # CHILDREN
        if profile.has_children is None:
            if 'çocuğum yok' in clean or 'çocuk yok' in clean or 'değilim' in clean:
                profile.has_children = False
                profile.family_size = 0
                profile.answered_categories.add(QuestionCategory.CHILDREN)
            elif 'çocuğum var' in clean or 'çocuk var' in clean:
                profile.has_children = True
                nums = re.findall(r'\d+', clean)
                profile.family_size = int(nums[0]) if nums else 1
                profile.answered_categories.add(QuestionCategory.CHILDREN)
                self.logger.info(f"✓ Extracted children: {profile.family_size}")
        
        # HOBBIES
        if not profile.hobbies:
            hobbies = ['spor', 'yüzme', 'koşu', 'futbol', 'basketbol', 'tenis', 'golf',
                      'okumak', 'kitap', 'müzik', 'sinema', 'tiyatro', 'yemek', 'seyahat',
                      'fotoğraf', 'resim', 'dans', 'yoga', 'pilates']
            for hobby in hobbies:
                if hobby in clean:
                    profile.hobbies = [hobby]
                    profile.answered_categories.add(QuestionCategory.HOBBIES)
                    self.logger.info(f"✓ Extracted hobby: {hobby}")
                    break
        
        # EMAIL
        email = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', msg)
        if email and not profile.email:
            profile.email = email.group()
            profile.answered_categories.add(QuestionCategory.EMAIL)
    
    def _get_missing_info(self, profile: UserProfile) -> list:
        """Get missing info."""
        missing = []
        
        if not profile.name:
            missing.append("isim")
        if not profile.hometown:
            missing.append("yaşadığı şehir")
        if not profile.profession:
            missing.append("meslek")
        if not profile.marital_status:
            missing.append("medeni durum")
        
        if profile.marital_status == "evli" and profile.has_children is None:
            missing.append("çocuk")
        
        if not profile.hobbies and QuestionCategory.HOBBIES not in profile.answered_categories:
            missing.append("hobi/ilgi alanları")
        
        # Home questions later
        basic_done = profile.name and profile.hometown and profile.profession
        if basic_done:
            if not profile.budget:
                missing.append("yaşam tercihleri")
            if not profile.location:
                missing.append("taşınma düşüncesi")
        
        return missing
    
    async def _generate_response(self, profile: UserProfile, conversation: Conversation, missing: list) -> str:
        """Generate with STRONG memory awareness."""
        try:
            history = self._get_history(conversation, 8)
            memory = self._get_detailed_memory(profile)
            
            prompt = f"""KULLANICI HAKKINDA BİLİNENLER (ÇOK ÖNEMLİ - BUNLARI ASLA TEKRAR SORMA):
{memory}

SON SOHBET (kullanıcının verdiği tüm cevaplar burada):
{history}

EKSİK BİLGİLER: {', '.join(missing) if missing else 'Temel bilgiler tamam'}

GÖREV:
Kullanıcının son mesajına samimi yanıt ver ve eksik bilgilerden birini öğren.

KRİTİK KURALLAR:
- BİLİNEN bilgileri ASLA tekrar sorma!
- Kullanıcı zaten cevap verdiyse GEÇMEDE görünüyor, tekrar sorma!
- 3-5 cümle
- Adın yok, sadece "AI asistan" de
- Doğal geçişler

{"⚠️ İSİM BİLİNİYOR: " + profile.name if profile.name else "İsim bilinmiyor"}
{"⚠️ MESLEK BİLİNİYOR: " + profile.profession + " - TEKRAR SORMA!" if profile.profession else "Meslek bilinmiyor"}
{"⚠️ ŞEHİR BİLİNİYOR: " + profile.hometown + " - TEKRAR SORMA!" if profile.hometown else "Şehir bilinmiyor"}

Yanıt:"""

            response = await self.question_agent.llm_service.generate_response(
                prompt=prompt,
                system_message=SYSTEM_PROMPT,
                temperature=0.85,
                max_tokens=200
            )
            
            result = response.strip()
            
            # Remove any prefix
            if ":" in result and result.split(":")[0] in ["A", "Ayşe", "Bot", "Asistan"]:
                result = result.split(":", 1)[1].strip()
            
            return result
            
        except Exception as e:
            self.logger.error(f"Generate error: {e}")
            if not profile.name:
                return "Merhaba! Ben AI emlak asistanıyım. Seninle tanışmak isterim, adın ne?"
            return f"Devam edelim {profile.name}!"
    
    def _get_history(self, conversation: Conversation, count: int = 8) -> str:
        """Get detailed history."""
        recent = conversation.get_recent_messages(count)
        if not recent:
            return "Yeni sohbet başladı"
        
        lines = []
        for msg in recent:
            role = "Kullanıcı" if msg.role.value == "user" else "Asistan"
            lines.append(f"{role}: {msg.content}")
        return "\n".join(lines)
    
    def _get_detailed_memory(self, profile: UserProfile) -> str:
        """Get detailed memory."""
        parts = []
        if profile.name:
            parts.append(f"✓ İsim: {profile.name}")
        if profile.hometown:
            parts.append(f"✓ Yaşadığı şehir: {profile.hometown}")
        if profile.profession:
            parts.append(f"✓ Meslek: {profile.profession}")
        if profile.marital_status:
            parts.append(f"✓ Medeni durum: {profile.marital_status}")
        if profile.has_children is not None:
            parts.append(f"✓ Çocuk: {'var' if profile.has_children else 'yok'}")
        if profile.hobbies:
            parts.append(f"✓ Hobi: {', '.join(profile.hobbies)}")
        
        return "\n".join(parts) if parts else "Henüz bilgi yok"
    
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
