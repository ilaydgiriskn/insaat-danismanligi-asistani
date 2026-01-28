"""Process user message - Natural conversation with strong memory."""

from typing import Optional
from uuid import UUID
from datetime import datetime
from pathlib import Path
import os
import re
import json
from difflib import get_close_matches

from application.agents import QuestionAgent, ValidationAgent, AnalysisAgent
from domain.entities import UserProfile, Conversation
from domain.repositories import IUserRepository, IConversationRepository
from domain.enums import QuestionCategory
from infrastructure.config import get_logger
from infrastructure.llm import InformationExtractor


GREETINGS = {'merhaba', 'selam', 'selamlar', 'mrb', 'slm', 'hey', 'hi', 'sa', 'merhabalar', 'naber'}

SYSTEM_PROMPT = """Sen bir AI Emlak Danışmanısın.
Görevin: Kullanıcıyla GÜNLÜK, DOĞAL ve KISA sohbet ederek, kullanıcının KONUT İHTİYAÇLARINI ve EVLE İLİŞKİLİ yaşam tarzını anlamak.

❗ ANA AMAÇ DIŞINA ÇIKMA YASAK. Tanışma sohbeti değil, sonuç odaklı danışmanlık.

KONUŞMA KURALLARI (ÇOK ÖNEMLİ):
1. **SADECE AMACA YÖNELİK SORU**: Müzik, aile veya hobi sadece ev tercihlerini (oda sayısı, yalıtım, konum vb.) etkiliyorsa sor. Süsleme, edebiyat, nostalji YASAK.
2. **TEK MESAJ TEK SORU**: Her mesajda SADECE 1 soru sor. Asla 2 soru sorma. Seçenekli uzun sorular sorma.
3. **TEKRAR YASAK**: Kullanıcının verdiği bilgiyi (örn: "5 kişilik aile") cevapta tekrar etme. (Yanlış: "5 kişilik aileniz için...", Doğru: "Oda dağılımı bu durumda önemli...")
4. **DİL**: 2-3 kısa cümle. Net, duru, günlük. Metafor ve övgü yok.
5. **İSİM-SOYİSİM**: İlk başta sadece İSİM sor. Soyisimi EN SONDA iletişim bilgileriyle al.
6. **HIZ**: Gereksiz özetleme yapma. Hızlı ilerle.

EV ODAĞI KONTROLÜ:
Sorduğun her soru şu testten geçmeli: "Bu soru kullanıcının ev tercihini anlamama yardım ediyor mu?" Cevap hayırsa SORMA.

BİLGİ TOPLAMA SIRASI (Esnek ama hedefli):
1. İsim (Sadece ön ad)
2. Mevcut Konum & Memleket
3. Meslek & Maaş (Bütçe için kritik)
4. Aile/Medeni Durum (Oda sayısı için)
5. Evle İlgili Hobiler (Spor, müzik, mutfak vb.)
6. **FİNAL**: Soyisim, Telefon, Email.

TON: Arkadaş gibi ama ciddi, iş bitirici bir danışman."""


class ProcessUserMessageUseCase:
    """Advanced real estate consultant with strategic guidance."""
    
    def __init__(
        self,
        user_repository: IUserRepository,
        conversation_repository: IConversationRepository,
        question_agent: QuestionAgent,
        validation_agent: ValidationAgent,
        analysis_agent: AnalysisAgent,
        information_extractor: InformationExtractor,
    ):
        self.user_repo = user_repository
        self.conversation_repo = conversation_repository
        self.question_agent = question_agent
        self.validation_agent = validation_agent
        self.analysis_agent = analysis_agent
        self.info_extractor = information_extractor
        self.logger = get_logger(self.__class__.__name__)
    
    async def execute(self, session_id: str, user_message: str) -> dict:
        """Process message with strategic advisor logic."""
        try:
            profile = await self._get_or_create_profile(session_id)
            conversation = await self._get_or_create_conversation(profile.id)
            
            conversation.add_user_message(user_message)
            
            # 1. Extract info from current message using LLM (with history for context)
            history_str = self._get_history(conversation, 5)
            await self._update_profile_from_message(profile, user_message, history_str)
            
            # Keep manual fallbacks for basic things (optional but safe)
            self._extract_all_info(profile, user_message)
            
            # 2. Perform strategic analysis (internal)
            # Pass full history for deep Agent 2 analysis (defensive conversion)
            history_messages = conversation.get_recent_messages(20)
            history_dicts = []
            for m in history_messages:
                if hasattr(m, 'to_dict'):
                    history_dicts.append(m.to_dict())
                else:
                    history_dicts.append({"role": getattr(m, 'role', 'user'), "content": getattr(m, 'content', str(m))})
            
            advisor_analysis = await self.analysis_agent.execute(profile, chat_history=history_dicts)
            
            self.logger.info(f"Advisor Analysis result: {json.dumps(advisor_analysis.get('structured_analysis'), ensure_ascii=False) if advisor_analysis.get('structured_analysis') else 'Heuristic/Fallback'}")
            
            await self.user_repo.update(profile)
            await self.conversation_repo.update(conversation)
            
            # 3. Check for Phase Transition (Agent 2)
            # Use ValidationAgent to see if we are ready for final recommendations
            validation_result = await self.validation_agent.execute(profile)
            is_ready = validation_result.get("is_ready_for_analysis", False)
            
            # Get missing info for context (used in Agent 1 phase)
            missing = self._get_missing_info(profile)
            
            if is_ready:
                # PHASE 2: Profile Complete - Silent transition to Guidance (Agent 2)
                self.logger.info(f"Profile complete for {profile.name} {profile.surname}. Transitioning to Guidance.")
                
                # CRM EXPORT: Silent background report
                crm_report = self._generate_crm_report(profile, advisor_analysis)
                self._save_crm_report_to_file(crm_report, profile)
                
                # Use Agent 2's guidance message instead of a goodbye
                response = advisor_analysis.get("guidance_cue", "Hayalindeki evi bulmak için kriterlerin üzerinden geçmeye devam edebiliriz.")
            else:
                # PHASE 1: Information Gathering / Discovery (Agent 1)
                response = await self._generate_response(profile, conversation, missing, advisor_analysis)
            
            conversation.add_assistant_message(response)
            await self.conversation_repo.update(conversation)
            
            return {
                "response": response,
                "type": "analysis" if is_ready else "question",
                "is_complete": is_ready,
                "category": None,
            }
            
        except Exception as e:
            self.logger.error(f"Error: {e}", exc_info=True)
            return {
                "response": "Pardon, bir aksaklık oldu. Devam edelim mi?",
                "type": "error",
                "is_complete": False,
            }
    
    async def _update_profile_from_message(self, profile: UserProfile, message: str, history: str) -> None:
        """Update profile using LLM-based information extractor."""
        try:
            extracted_info = await self.info_extractor.extract_profile_info(message, history)
            self.logger.info(f"Extracted info: {json.dumps(extracted_info, ensure_ascii=False)}")
            
            if not extracted_info:
                return

            # Map fields to UserProfile
            if extracted_info.get("name"): 
                profile.name = extracted_info["name"]
                profile.answered_categories.add(QuestionCategory.NAME)
            if extracted_info.get("surname"): 
                profile.surname = extracted_info["surname"]
                profile.answered_categories.add(QuestionCategory.SURNAME)
            if extracted_info.get("email"): profile.email = extracted_info["email"]
            if extracted_info.get("phone"): profile.phone_number = extracted_info["phone"]
            if extracted_info.get("hometown"): profile.hometown = extracted_info["hometown"]
            if extracted_info.get("profession"): profile.profession = extracted_info["profession"]
            if extracted_info.get("marital_status"): profile.marital_status = extracted_info["marital_status"]
            if extracted_info.get("has_children") is not None: profile.has_children = extracted_info["has_children"]
            
            if extracted_info.get("hobbies"):
                profile.hobbies = extracted_info["hobbies"]
            
            if extracted_info.get("budget"):
                from domain.value_objects import Budget
                try:
                    b_val = int(extracted_info["budget"])
                    profile.budget = Budget(min_amount=b_val, max_amount=b_val * 1.2, currency="TL")
                except:
                    pass
            
            if extracted_info.get("hometown"): 
                profile.hometown = extracted_info["hometown"]
                profile.answered_categories.add(QuestionCategory.HOMETOWN)
            
            if extracted_info.get("location"):
                from domain.value_objects import Location
                profile.location = Location(city=extracted_info["location"], country="Turkey")
                profile.answered_categories.add(QuestionCategory.LOCATION)
            if extracted_info.get("rooms"):
                from domain.value_objects import PropertyPreferences
                from domain.enums import PropertyType
                if not profile.property_preferences:
                    profile.property_preferences = PropertyPreferences(property_type=PropertyType.APARTMENT, min_rooms=int(extracted_info["rooms"]))
                else:
                    profile.property_preferences.min_rooms = int(extracted_info["rooms"])

            # Sync answered categories
            if extracted_info.get("answered_categories"):
                for cat_name in extracted_info["answered_categories"]:
                    try:
                        cat_enum = QuestionCategory[cat_name.upper()]
                        profile.answered_categories.add(cat_enum)
                    except (KeyError, ValueError):
                        pass

            # Update lifestyle notes and salary info
            if extracted_info.get("lifestyle_notes"):
                profile.lifestyle_notes = extracted_info["lifestyle_notes"]
            if extracted_info.get("estimated_salary_range"):
                profile.estimated_salary = extracted_info["estimated_salary_range"]

        except Exception as e:
            self.logger.error(f"Error in _update_profile_from_message: {str(e)}", exc_info=True)

    def _extract_all_info(self, profile: UserProfile, message: str) -> None:
        """Simple manual extraction fallback (optional since LLM does the main work)."""
        msg = message.strip()
        msg_lower = msg.lower()
        
        # Clean message
        clean = msg_lower.replace(" sen", "").replace("sen ", "").replace("senin", "").strip()
        
        # Skip greetings
        if clean in GREETINGS:
            return
        
        # NAME extraction (Simple first word fallback if name is completely missing)
        if not profile.name and len(clean.split()) <= 4:
            # Look for "adım X" pattern
            name_match = re.search(r'ad[iıî]m\s+(\w+)', clean)
            if name_match:
                profile.name = name_match.group(1).title()
                profile.answered_categories.add(QuestionCategory.NAME)
                return
            
            # Very short message might be a name
            words = [w for w in clean.split() if w not in GREETINGS and w not in ['benim', 'adım', 'ben', 'evet', 'hayır', 'var', 'yok']]
            if len(words) == 1 and 2 < len(words[0]) < 15:
                # Basic check to avoid common words, but LLM will correct this if wrong
                if words[0] not in ['doktor', 'istanbul', 'ankara', 'evet']:
                    profile.name = words[0].title()
                    profile.answered_categories.add(QuestionCategory.NAME)
                    return
        
        # Note: City, Profession, Hobbies etc. are now handled 100% by the LLM-based 
        # _update_profile_from_message method which supports all of Turkey's districts.
        return
        
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
    
    async def _generate_response(self, profile: UserProfile, conversation: Conversation, missing: list, advisor_analysis: dict) -> str:
        """Generate with focus on ESSENTIAL info and Advisor Guidance."""
        try:
            history = self._get_history(conversation, 8)
            memory = self._get_detailed_memory(profile)
            
            # Advisor Context
            pkg = advisor_analysis.get("package_info", {})
            guidance = advisor_analysis.get("guidance_cue", "")
            is_mature = advisor_analysis.get("is_profile_mature", False)
            
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
            
            # Build known items list
            known_str = self._get_detailed_memory(profile)
            
            if not is_mature:
                phase_instruction = """Şu an TANIŞMA aşamasındasın. 
- ASLA evlerden, fiyatlardan veya bütçe yeterliliğinden bahsetme.
- Sadece samimi bir sohbet kur ve hobileri yaşam alanına bağla."""
            else:
                phase_instruction = f"""Şu an YÖNLENDİRME aşamasındasın.
- Tavsiye edilen yönlendirmeyi (guidance_cue) doğal bir şekilde cümlene ekle: "{guidance}"
- KESİNLİKLE "A segmenti", "B paketi" gibi terimler kullanma. Sadece özellikleri anlat.
- Bütçe 7M altındaysa (Örn: 6M), onu 7M bandındaki (Tier A) ferahlığın hayatını nasıl değiştireceğine nazikçe ikna et."""

            message_text = f"""BİLGE DANIŞMAN ANALİZİ:
- Mevcut Profil: {known_str}
- Tavsiye Edilen Yönlendirme: "{guidance}"
- Profil Olgunluğu: {"Olgun" if is_mature else "Henüz Tanışma"}

{phase_instruction}

SON SOHBET:
{history}

EKSİK BİLGİ ALANLARI: {', '.join(missing) if missing else 'Kritik veriler tam.'}

GÖREV:
1. Kullanıcının mesajına BİLGECE, EMPATİK ve VİZYONER bir yanıt ver.
2. Bilgiyi yaşam alanı vizyonuyla yorumla ama "ev" kelimesini kullanma (Agent 1 ise).
3. HEMEN BİR SONRAKİ KATEGORİYE GEÇ VE SADECE BİR (1) SORU SOR.
4. CEVAP 3-4 CÜMLE OLSUN. Duygusuz ve bot gibi konuşma.

Yanıt:"""

            response = await self.question_agent.llm_service.generate_response(
                prompt=message_text,
                system_message=SYSTEM_PROMPT,
                temperature=0.7,  # Bir tık daha stabil olsun
                max_tokens=250
            )
            
            result = response.strip()
            
            # Remove prefix
            if ":" in result and result.split(":")[0] in ["A", "Ayşe", "Bot", "Asistan", "Danışman"]:
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
                return "Sohbetimize devam edelim, isminiz nedir?"
            return f"Sizinle ilgili daha fazla şey öğrenmek beni mutlu ediyor {profile.name}. Hayatınızın bu döneminde sizi neler heyecanlandırıyor?"
    
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
    
    def _generate_crm_report(self, profile: UserProfile, advisor_analysis: dict) -> dict:
        """Generate comprehensive CRM report for real estate agent."""
        structured = advisor_analysis.get("structured_analysis", {})
        user_analysis = structured.get("user_analysis", {}) if structured else {}
        budget_eval = structured.get("budget_evaluation", {}) if structured else {}
        
        return {
            "rapor_tarihi": datetime.now().isoformat(),
            "musteri_bilgileri": {
                "isim": profile.name,
                "telefon": profile.phone_number,
                "email": profile.email,
                "memleket": profile.hometown,
            },
            "profesyonel_bilgiler": {
                "meslek": profile.profession,
                "tahmini_maas": profile.estimated_salary,
            },
            "aile_bilgileri": {
                "medeni_durum": profile.marital_status,
                "cocuk_var_mi": profile.has_children,
                "aile_buyuklugu": profile.family_size,
            },
            "yasam_tarzi": {
                "hobiler": profile.hobbies,
            },
            "konut_tercihleri": {
                "hedef_sehir": profile.location.city if profile.location else profile.hometown,
                "hedef_ilce": profile.location.district if profile.location and hasattr(profile.location, 'district') else None,
                "oda_sayisi": profile.property_preferences.min_rooms if profile.property_preferences else None,
                "ev_tipi": profile.property_preferences.property_type.value if profile.property_preferences and profile.property_preferences.property_type else None,
            },
            "butce_analizi": {
                "belirtilen_butce": profile.budget.max_amount if profile.budget else None,
                "para_birimi": profile.budget.currency if profile.budget else "TRY",
                "tavsiye_edilen_segment": user_analysis.get("estimated_budget_segment", "A"),
                "guven_seviyesi": user_analysis.get("confidence_level", "medium"),
                "ust_segmente_gecis_mumkun": budget_eval.get("upper_segment_possible"),
                "ek_butce_gerekli": budget_eval.get("additional_budget_needed"),
            },
            "ai_degerlendirmesi": {
                "risk_istahi": user_analysis.get("risk_appetite", "orta"),
                "satin_alma_motivasyonu": user_analysis.get("purchase_motivation", "yasam"),
                "satin_alma_zamani": user_analysis.get("purchase_timeline", "belirsiz"),
                "yasam_tarzi_notlari": structured.get("lifestyle_insights", []) if structured else [],
            },
            "status": "PROFIL_TAMAMLANDI_EMLAKCIYA_GONDERILDI"
        }
    
    def _save_crm_report_to_file(self, crm_report: dict, profile: UserProfile) -> str:
        """Save CRM report to a JSON file for the real estate agent."""
        try:
            # Create reports directory if it doesn't exist
            reports_dir = Path(__file__).parent.parent.parent.parent / "customer_reports"
            reports_dir.mkdir(exist_ok=True)
            
            # Generate filename with customer name and timestamp
            customer_name = (profile.name or "unknown").lower().replace(" ", "_")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{customer_name}_{timestamp}.json"
            filepath = reports_dir / filename
            
            # Write report to file
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(crm_report, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"CRM report saved to: {filepath}")
            return str(filepath)
            
        except Exception as e:
            self.logger.error(f"Failed to save CRM report: {e}")
            return "DOSYA_KAYIT_HATASI"
