"""Process user message - Natural conversation with strong memory."""

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
- Adın YOK, sadece "AI asistan"
- "Senin adın ne?" → "Ben AI emlak asistanıyım"

ZORUNLU BİLGİLER (sırayla topla):
1. İsim, şehir, meslek
2. Medeni durum, çocuk sayısı
3. Hobi (kısaca)
4. ✓ Mail adresi (MUTLAKA)
5. ✓ Telefon (MUTLAKA)
6. ✓ Aylık gelir/maaş (MUTLAKA)
7. ✓ Kaç odalı ev istediği (MUTLAKA)
8. Hedef şehir (taşınacaksa)

YASAK KONULAR:
❌ İç dekorasyon detayları
❌ Oda tasarımı (pilot temalı vb.)
❌ Mobilya, renk, stil
❌ Mimarlık detayları
→ Sadece GENEL bilgi topla (kaç oda, bahçe var mı gibi)

HAFIZA KURALLARI:
- Kullanıcının söylediği HER ŞEYİ hatırla
- Zaten bilinenler EKSİK listesinde GÖRÜNMEMELİ
- Çocuk yaşı söylediyse UNUTMA

SOHBET TARZI:
- 3-4 cümle
- Doğal, samimi
- Zorlamadan geç

Türkçe, odaklı, hafızalı."""


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
            self.logger.info(f"STATE: name={profile.name}, city={profile.hometown}, job={profile.profession}")
            
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
                self.logger.info(f"Extracted name: {profile.name}")
                return
            
            # Short message without question words might be name
            words = [w for w in clean.split() if w not in GREETINGS and w not in ['benim', 'adım', 'ben', 'evet', 'hayır', 'var', 'yok']]
            if words and len(words[0]) > 1 and len(words[0]) < 15:
                potential_name = words[0]
                # Not a city or profession
                if potential_name not in self.CITIES and potential_name not in ['doktor', 'mühendis', 'öğretmen']:
                    profile.name = potential_name.title()
                    profile.answered_categories.add(QuestionCategory.NAME)
                    self.logger.info(f"Extracted name: {profile.name}")
                    return
        
        # CITY extraction with FUZZY matching
        city_found = False
        for city in self.CITIES:
            if city in clean:
                if not profile.hometown:
                    profile.hometown = city.title()
                    profile.answered_categories.add(QuestionCategory.HOMETOWN)
                    self.logger.info(f"Extracted city (exact): {profile.hometown}")
                    city_found = True
                elif not profile.location:
                    from domain.value_objects import Location
                    profile.location = Location(city=city.title(), country="Turkey")
                    profile.answered_categories.add(QuestionCategory.LOCATION)
                    self.logger.info(f"Extracted target city: {city}")
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
                            self.logger.info(f"Extracted city (fuzzy): {profile.hometown}")
                        elif not profile.location:
                            from domain.value_objects import Location
                            profile.location = Location(city=city.title(), country="Turkey")
                            profile.answered_categories.add(QuestionCategory.LOCATION)
                        break
        
        # PROFESSION extraction
        if not profile.profession:
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
                'yazılım': 'Yazılımcı',
                'software': 'Yazılımcı',
                'developer': 'Yazılımcı',
            }
            
            for key, value in professions.items():
                if key in clean:
                    profile.profession = value
                    profile.answered_categories.add(QuestionCategory.PROFESSION)
                    self.logger.info(f"Extracted profession: {profile.profession}")
                    break
            
            # "X sektörü" pattern
            if not profile.profession:
                sector_match = re.search(r'(\w+)\s+sekt[öo]r', clean)
                if sector_match:
                    sector = sector_match.group(1)
                    if sector == 'yazılım' or sector == 'yazilim':
                        profile.profession = 'Yazılımcı'
                    else:
                        profile.profession = sector.title() + ' Sektörü'
                    profile.answered_categories.add(QuestionCategory.PROFESSION)
                    self.logger.info(f"Extracted profession (sector): {profile.profession}")
        
        # MARITAL STATUS
        if not profile.marital_status:
            if 'evliyim' in clean or 'evli' in clean:
                profile.marital_status = "evli"
                profile.answered_categories.add(QuestionCategory.MARITAL_STATUS)
            elif 'bekarım' in clean or 'bekar' in clean:
                profile.marital_status = "bekar"
                profile.answered_categories.add(QuestionCategory.MARITAL_STATUS)
        
        # CHILDREN
        if profile.has_children is None:
            if 'çocuğum yok' in clean or 'çocuk yok' in clean:
                profile.has_children = False
                profile.family_size = 0
                profile.answered_categories.add(QuestionCategory.CHILDREN)
            elif 'çocuğum var' in clean or 'çocuk var' in clean:
                profile.has_children = True
                nums = re.findall(r'\d+', clean)
                profile.family_size = int(nums[0]) if nums else 1
                profile.answered_categories.add(QuestionCategory.CHILDREN)
        
        # HOBBIES
        if not profile.hobbies:
            hobbies_list = ['spor', 'yüzme', 'koşu', 'futbol', 'basketbol', 'tenis', 'golf',
                          'okumak', 'kitap', 'müzik', 'sinema', 'tiyatro', 'yemek', 'seyahat']
            for hobby in hobbies_list:
                if hobby in clean:
                    profile.hobbies = [hobby]
                    profile.answered_categories.add(QuestionCategory.HOBBIES)
                    break
        
        # EMAIL
        email = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', msg)
        if email and not profile.email:
            profile.email = email.group()
            profile.answered_categories.add(QuestionCategory.EMAIL)
        
        # PHONE
        if not profile.phone_number:
            phone_patterns = [
                r'(\+90\s?\d{3}\s?\d{3}\s?\d{2}\s?\d{2})',
                r'(0\d{3}\s?\d{3}\s?\d{2}\s?\d{2})',
                r'(\d{10})',
            ]
            for pattern in phone_patterns:
                match = re.search(pattern, msg.replace('-', '').replace('(', '').replace(')', ''))
                if match:
                    profile.phone_number = match.group(1)
                    profile.answered_categories.add(QuestionCategory.PHONE_NUMBER)
                    break
        
        # SALARY
        if not profile.estimated_salary:
            salary_patterns = [
                r'(\d+)\s*(bin|k)',
                r'maaş[ıi]m?\s+(\d+)',
                r'gelir[im]?\s+(\d+)',
                r'(\d+)\s*tl',
            ]
            for pattern in salary_patterns:
                match = re.search(pattern, clean)
                if match:
                    amount = match.group(1)
                    try:
                        salary = int(amount)
                        if 'bin' in clean or 'k' in clean:
                            salary = salary * 1000
                        elif salary < 1000:
                            salary = salary * 1000
                        profile.estimated_salary = str(salary)
                        profile.answered_categories.add(QuestionCategory.ESTIMATED_SALARY)
                        break
                    except:
                        pass
        
        # ROOM COUNT
        if not profile.property_preferences or not profile.property_preferences.min_rooms:
            room_patterns = [
                r'(\d+)\s*(oda|odalı)',
                r'(\d+)\+\d+',
            ]
            for pattern in room_patterns:
                match = re.search(pattern, clean)
                if match:
                    rooms = int(match.group(1))
                    from domain.value_objects import PropertyPreferences
                    from domain.enums import PropertyType
                    profile.property_preferences = PropertyPreferences(
                        property_type=PropertyType.APARTMENT,
                        min_rooms=rooms
                    )
                    profile.answered_categories.add(QuestionCategory.ROOMS)
                    break
    
    def _get_missing_info(self, profile: UserProfile) -> list:
        """Get missing info - ESSENTIAL first."""
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
            missing.append("çocuk var mı")
        
        if not profile.hobbies and QuestionCategory.HOBBIES not in profile.answered_categories:
            missing.append("hobi (kısaca)")
        
        # ESSENTIAL INFO
        if not profile.email:
            missing.append("EMAIL (zorunlu)")
        if not profile.phone_number:
            missing.append("TELEFON (zorunlu)")
        if not profile.estimated_salary:
            missing.append("AYLIK GELİR (zorunlu)")
        
        if not profile.property_preferences or not profile.property_preferences.min_rooms:
            missing.append("KAÇ ODALI EV (zorunlu)")
        
        if not profile.location:
            missing.append("taşınma düşüncesi")
        
        if not profile.budget:
            missing.append("bütçe aralığı")
        
        return missing
    
    async def _generate_response(self, profile: UserProfile, conversation: Conversation, missing: list) -> str:
        """Generate with focus on ESSENTIAL info."""
        try:
            history = self._get_history(conversation, 8)
            memory = self._get_detailed_memory(profile)
            
            # Separate essential from optional
            essential = [m for m in missing if 'zorunlu' in m]
            optional = [m for m in missing if 'zorunlu' not in m]
            
            # Build known items list
            known_items = []
            if memory != "Henüz bilgi yok":
                for line in memory.split("\n"):
                    if line.startswith("✓"):
                        parts = line.split(":", 1)
                        if len(parts) == 2:
                            known_items.append(parts[1].strip())
            
            known_str = ", ".join(known_items) if known_items else ""
            
            message_text = f"KULLANICI HAKKINDA BİLİNENLER:\n{memory}\n\nSON SOHBET:\n{history}\n\nZORUNLU EKSİK BİLGİLER (öncelik): {', '.join(essential) if essential else 'Tamamlandı'}\nDİĞER EKSİK: {', '.join(optional) if optional else 'Tamam'}\n\nGÖREV:\nKullanıcının son mesajına samimi yanıt ver ve SONRAKİ eksik bilgiyi öğren.\n\nKRİTİK KURALLAR:\n- İÇ DEKORASYON, TASARIM, MOBİLYA KONUŞMA!\n- Sadece genel bilgi topla\n- Zaten bilinen şeyleri ASLA tekrar sorma\n- 3-4 cümle\n- Adın yok\n\nBİLİNEN: {known_str}\n\nYanıt:"

            response = await self.question_agent.llm_service.generate_response(
                prompt=message_text,
                system_message=SYSTEM_PROMPT,
                temperature=0.8,
                max_tokens=150
            )
            
            result = response.strip()
            
            # Remove prefix
            if ":" in result and result.split(":")[0] in ["A", "Ayşe", "Bot", "Asistan"]:
                result = result.split(":", 1)[1].strip()
            
            return result
            
        except Exception as e:
            self.logger.error(f"Generate error: {e}")
            # If LLM fails, use deterministic QuestionAgent for a smart question
            try:
                agent_result = await self.question_agent.execute(profile, conversation)
                if agent_result.get("question"):
                    self.logger.info("Using QuestionAgent fallback")
                    return agent_result["question"]
            except:
                pass
                
            if not profile.name:
                return "Merhaba! Ben AI emlak asistanıyım. Adın ne?"
            return f"{profile.name}, devam edelim. Hangi şehirde ev arıyorsun?"
    
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
        """Get detailed memory with child info."""
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
            if profile.has_children:
                age_info = f" ({profile.family_size} çocuk)" if profile.family_size else " (var)"
                parts.append(f"✓ Çocuk: var{age_info}")
            else:
                parts.append("✓ Çocuk: yok")
        if profile.hobbies:
            parts.append(f"✓ Hobi: {', '.join(profile.hobbies)}")
        if profile.email:
            parts.append(f"✓ Email: {profile.email}")
        if profile.phone_number:
            parts.append(f"✓ Telefon: {profile.phone_number}")
        if profile.estimated_salary:
            parts.append(f"✓ Maaş: {profile.estimated_salary}")
        
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
