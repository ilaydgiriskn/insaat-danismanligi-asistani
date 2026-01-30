"""Process user message - Natural conversation with strong memory."""

from typing import Optional
from uuid import UUID
from datetime import datetime
from pathlib import Path
import os
import re
import json
import asyncio
from difflib import get_close_matches

from application.agents import QuestionAgent, ValidationAgent, AnalysisAgent
from domain.entities import UserProfile, Conversation
from domain.repositories import IUserRepository, IConversationRepository
from domain.enums import QuestionCategory
from infrastructure.config import get_logger
from infrastructure.reporting.smtp_client import send_report_via_email # Added
from infrastructure.llm import InformationExtractor
from infrastructure.reporting.pdf_generator import PDFReportGenerator


GREETINGS = {'merhaba', 'selam', 'selamlar', 'mrb', 'slm', 'hey', 'hi', 'sa', 'merhabalar', 'naber'}


SYSTEM_PROMPT = """Sen samimi, dikkatli ve zeki bir Emlak Asistanısın.
Görevin: Kullanıcıyı doğal bir sohbetle tanı.
ZORUNLU BİLGİLER: İsim, Soyisim, Meslek, Maaş, Email, Yaşadığı Şehir ve Semt.

TON: Arkadaşça, güven veren, robotiklikten uzak. Yanıtların 2-3 cümle olsun."""


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
            
            # 1. PARALLEL EXECUTION: Extraction & Analysis
            # Run LLM extraction and Advisor Analysis at the same time to save 3-5 seconds.
            history_str = self._get_history(conversation, 5)
            
            # Prepare Analysis Input (using current profile state)
            history_messages = conversation.get_recent_messages(20)
            history_dicts = []
            for m in history_messages:
                if hasattr(m, 'to_dict'):
                    history_dicts.append(m.to_dict())
                else:
                    history_dicts.append({"role": getattr(m, 'role', 'user'), "content": getattr(m, 'content', str(m))})
            
            # Execute both concurrently
            warnings, advisor_analysis = await asyncio.gather(
                self._update_profile_from_message(profile, user_message, history_str),
                self.analysis_agent.execute(profile, chat_history=history_dicts)
            )
            
            # IMMEDIATE VALIDATION CHECK
            if warnings and "phone_invalid" in warnings:
                response = "Girdiğiniz telefon numarası eksik veya hatalı görünüyor (en az 10 hane olmalı). İletişim için önemli, lütfen kontrol edip tekrar yazar mısınız? 🙏"
                conversation.add_assistant_message(response)
                await self.conversation_repo.update(conversation)
                return {
                    "response": response,
                    "type": "question",
                    "is_complete": False,
                    "category": QuestionCategory.PHONE_NUMBER
                }
            
            # Keep manual fallbacks for basic things (optional but safe)
            self._extract_all_info(profile, user_message)
            
            self.logger.info(f"Advisor Analysis result: {json.dumps(advisor_analysis.get('structured_analysis'), ensure_ascii=False) if advisor_analysis.get('structured_analysis') else 'Heuristic/Fallback'}")
            
            await self.user_repo.update(profile)
            await self.conversation_repo.update(conversation)
            
            # 3. Check for Phase Transition (Agent 2)
            # Get missing info strict check
            missing = self._get_missing_info(profile)
            
            # DETERMINISTIC CHECK: Use missing info list, no LLM call needed
            is_ready = not missing
            if is_ready:
                self.logger.info("Deterministic Logic: All fields present -> Force Ready")
            else:
                self.logger.info(f"Missing fields: {missing}")
            
            if is_ready:
                # PHASE 2: Profile Complete
                
                # Check if we ALREADY transitioned (to avoid infinite loop)
                last_msg = conversation.get_last_assistant_message()
                transition_phrase = "Raporunuz hazırlanıyor"
                
                if last_msg and transition_phrase in last_msg.content:
                    # Already transitioned -> Session Closed
                    self.logger.info("Session already closed.")
                    response = "Bütün bilgileriniz alınmıştır. Raporunuz e-posta adresinize gönderilecektir. Teşekkürler! 👋"
                    
                else:
                    # FIRST TIME Transition -> FINAL CLOSING
                    self.logger.info(f"Closing Session for: {profile.name}")
                    
                    # CRM EXPORT: Silent background report
                    crm_report = self._generate_crm_report(profile, advisor_analysis)
                    pdf_path = self._save_crm_report_to_file(crm_report, profile)
                    
                    # EMAIL REPORTING (Non-blocking) - Raporlar insaatproje8@gmail.com adresine gönderilir
                    email_body = f"Müşteri: {profile.name} {profile.surname}\n\n"
                    summary = advisor_analysis.get("structured_analysis", {}).get("summary", "Detaylı analiz ektedir.")
                    email_body += f"ANALİZ RAPORU ÖZETİ:\n{summary}\n\n"
                    email_body += "Detaylı rapor PDF olarak ektedir."
                    
                    try:
                        # Send to system email (insaatproje8@gmail.com)
                        send_report_via_email(email_body, recipient_email=None, subject=f"AI Analiz Raporu: {profile.name} {profile.surname}", attachment_path=pdf_path)
                    except Exception as e:
                        self.logger.error(f"Email trigger failed: {e}")
                    
                    # Final Closing Message - Samimi ve kişisel
                    response = f"{profile.name} Bey/Hanım, sizinle sohbet etmek gerçekten keyifliydi! 😊\n\nTüm bilgilerinizi detaylıca not ettim ve raporunuz hazırlandı.\n\nEv arayışınızda size en uygun seçenekleri sunmak için sabırsızlanıyorum. Kendinize iyi bakın! 🏠"


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
    
    async def _update_profile_from_message(self, profile: UserProfile, message: str, history: str) -> list:
        """Update profile and return validation warnings if any."""
        try:
            extracted_info = await self.info_extractor.extract_profile_info(message, history)
            self.logger.info(f"Extracted info: {json.dumps(extracted_info, ensure_ascii=False)}")
            
            if not extracted_info:
                return []
            
            warnings = extracted_info.get("validation_warnings", [])

            # Map fields to UserProfile
            # Map fields to UserProfile
            # PROTECT NAME: Only set if None (First correct name sticks)
            if extracted_info.get("name") and not profile.name: 
                profile.name = extracted_info["name"]
                profile.answered_categories.add(QuestionCategory.NAME)
            
            if extracted_info.get("surname") and not profile.surname: 
                profile.surname = extracted_info["surname"]
                profile.answered_categories.add(QuestionCategory.SURNAME)
            if extracted_info.get("email"): 
                profile.email = extracted_info["email"]
                profile.answered_categories.add(QuestionCategory.EMAIL)
            if extracted_info.get("phone"): profile.phone_number = extracted_info["phone"]
            if extracted_info.get("hometown"): 
                profile.hometown = extracted_info["hometown"]
                profile.answered_categories.add(QuestionCategory.HOMETOWN)
            if extracted_info.get("current_city"): 
                profile.current_city = extracted_info["current_city"]
                profile.answered_categories.add(QuestionCategory.HOMETOWN)
            if extracted_info.get("profession"): profile.profession = extracted_info["profession"]
            if extracted_info.get("marital_status"): profile.marital_status = extracted_info["marital_status"]
            if extracted_info.get("has_children") is not None: profile.has_children = extracted_info["has_children"]
            
            if extracted_info.get("hobbies"):
                profile.hobbies = extracted_info["hobbies"]
            
            # Step 2: Value Object Extraction (Budget, Location, Rooms)
            if extracted_info.get("budget"):
                from domain.value_objects import Budget
                try:
                    b_val = int(extracted_info["budget"])
                    # Create NEW instance (Budget is frozen)
                    profile.budget = Budget(min_amount=b_val, max_amount=b_val * 1.2, currency="TL")
                    profile.answered_categories.add(QuestionCategory.BUDGET)
                except: pass
            
            if extracted_info.get("location"):
                from domain.value_objects import Location
                # Create NEW instance (Location is frozen)
                profile.location = Location(city=extracted_info["location"], country="Turkey")
                profile.answered_categories.add(QuestionCategory.LOCATION)
            
            if extracted_info.get("rooms"):
                from domain.value_objects import PropertyPreferences
                from domain.enums import PropertyType
                try:
                    # Robust parsing for "3+1", "3", 3, "4 oda" etc.
                    raw_rooms = str(extracted_info["rooms"])
                    # Extract first number found
                    match = re.search(r'(\d+)', raw_rooms)
                    if match:
                        rooms_val = int(match.group(1))
                        
                        # Create NEW instance (PropertyPreferences is frozen)
                        if not profile.property_preferences:
                            profile.property_preferences = PropertyPreferences(property_type=PropertyType.APARTMENT, min_rooms=rooms_val)
                        else:
                            # Re-create with updated value
                            profile.property_preferences = PropertyPreferences(
                                property_type=profile.property_preferences.property_type,
                                min_rooms=rooms_val,
                                max_rooms=profile.property_preferences.max_rooms,
                                has_balcony=profile.property_preferences.has_balcony,
                                has_parking=profile.property_preferences.has_parking
                            )
                        profile.answered_categories.add(QuestionCategory.ROOMS)
                except: pass

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
            
            # Map monthly_income (number) to estimated_salary (str)
            if extracted_info.get("monthly_income"):
                profile.estimated_salary = str(extracted_info["monthly_income"])
                profile.answered_categories.add(QuestionCategory.ESTIMATED_SALARY)
            
            if extracted_info.get("social_amenities") is not None:
                profile.social_amenities = extracted_info["social_amenities"]
                profile.answered_categories.add(QuestionCategory.SOCIAL_AMENITIES)
                self.logger.info(f"Updated social amenities: {profile.social_amenities}")
            
            if extracted_info.get("purchase_purpose"):
                profile.purchase_purpose = extracted_info["purchase_purpose"]
                profile.answered_categories.add(QuestionCategory.PURCHASE_PURPOSE)

            # Update purchase_budget if explicitly provided
            if extracted_info.get("purchase_budget"):
                 # Create budget object logic here if needed, or update if existing
                 pass # Budget update is complex, handled by value object logic if needed. 
                 # For now, let's just note it. The Budget value object logic is separate.

            return warnings

        except Exception as e:
            self.logger.error(f"Error in _update_profile_from_message: {str(e)}", exc_info=True)
            return []

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
            words = [w for w in clean.split() if w not in GREETINGS and w not in ['benim', 'adım', 'ben', 'evet', 'hayır', 'var', 'yok', 'bilmiyorum', 'bilmem']]
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
        """Get missing info - Strictly follows User's Mandatory Fields rule."""
        missing = []
        
        # 1. ZORUNLU (Mandatory) - Agent 2'ye geçiş için şart
        if not profile.name:
            missing.append("isim")
        if not profile.surname:
            missing.append("soyisim")
        if not profile.profession:
            missing.append("meslek")
        if not profile.estimated_salary:
            missing.append("aylık gelir")
        
        # İletişim Bilgileri (Email Zorunlu, Telefon Sorulmalı)
        if not profile.email:
            missing.append("e-posta adresi ve telefon numarası")
        elif not profile.phone_number and not profile.has_answered_category(QuestionCategory.PHONE_NUMBER):
            missing.append("telefon numarası")
        
        if not profile.current_city:
            missing.append("yaşadığı şehir ve semt")
        
        # 2. OPSİYONEL AMA SORULMALI (Nice to have before analysis)
        if not profile.property_preferences or not profile.property_preferences.min_rooms:
            missing.append("istenen oda sayısı")
        if not profile.marital_status:
            missing.append("medeni durum")
        
        # 3. DURUMA BAĞLI ZORUNLU (Conditional)
        # Eğer evli ise çocuk durumu sorulmalı
        if profile.marital_status and "evli" in profile.marital_status.lower() and profile.has_children is None:
            missing.append("çocuk durumu")
        
        # 4. SORULMASI ZORUNLU (Must Ask - Even if answer is 'None')
        # Hometown (nereli olduğu)
        if not profile.hometown:
             missing.append("memleket")

        if not profile.has_answered_category(QuestionCategory.SOCIAL_AMENITIES):
             missing.append("sosyal alan tercihleri")
        
        # Satın Alma Amacı (Yatırım mı Oturum mu?)
        if not profile.purchase_purpose:
             missing.append("satın alma amacı")

        return missing
    
    async def _generate_response(self, profile: UserProfile, conversation: Conversation, missing: list, advisor_analysis: dict) -> str:
        """Generate with focus on Discovery (Phase 1) or Guidance (Phase 2)."""
        try:
            is_mature = advisor_analysis.get("is_profile_mature", False)
            
            # PHASE 1: Discovery (Keşif Sohbeti)
            # FORCE Phase 1 if there are missing fields, regardless of advisor opinion
            if missing or not is_mature:
                self.logger.info("Executing QuestionAgent for Discovery Phase")
                agent_result = await self.question_agent.execute(profile, conversation, missing)
                
                msg = (agent_result.get("message") or "").strip()
                q = (agent_result.get("question") or "").strip()
                
                # REPETITION GUARD
                # Check if 'q' (the question) was already asked recently or if the user already answered it logic
                recent_assistant_msgs = [m.content for m in conversation.messages if m.role.value == 'assistant'][-3:]
                if any(q in prev for prev in recent_assistant_msgs):
                     self.logger.warning(f"Prevented repetitive question: {q}")
                     # Fallback to general encouragement or next missing item
                     q = "" 

                if q:
                    # Defensive check: If question is already in message (case-insensitive), don't append it again
                    if q.lower() in msg.lower():
                        response = msg
                    else:
                        response = f"{msg} {q}"
                else:
                    response = msg or "Sohbetimiz için çok teşekkürler."
                
                return response

            # PHASE 2: Guidance (Yönlendirme)
            history = self._get_history(conversation, 8)
            guidance = advisor_analysis.get("guidance_cue", "")
            known_str = self._get_detailed_memory(profile)
            
            message_text = f"""BİLGE DANIŞMAN ANALİZİ:
- Mevcut Profil: {known_str}
- Tavsiye Edilen Yönlendirme: "{guidance}"

Şu an YÖNLENDİRME aşamasındasın.
- Tavsiye edilen yönlendirmeyi (guidance_cue) doğal bir şekilde cümlene ekle: "{guidance}"
- KESİNLİKLE "A segmenti", "B paketi" gibi terimler kullanma. Sadece özellikleri anlat.
- Bütçe 7M altındaysa onu Tier A (7M-9M) bandına nazikçe teşvik et.

SON SOHBET:
{history}

GÖREV:
1. Kullanıcının mesajına SAMİMİ, DOĞAL ve PROFESYONEL bir yanıt ver.
2. CEVAP MUTLAKA 2-3 CÜMLE OLSUN.
3. Arka plandaki uzmanlığını hissettir ama üstten bakma.
4. SOHBETİ SONLANDIRMA PLANI:
   - Bu aşamada kullanıcının ihtiyacını tam anlamak için EN FAZLA 2-3 stratejik soru daha sorabilirsin.
   - Eğer yeterince bilgi aldığını düşünüyorsan veya kullanıcı teşekkür ederse, nazikçe "Size özel raporumu hazırlıyorum, en kısa sürede iletişime geçeceğim" diyerek sohbeti sonlandır.
   - Sonsuza kadar soru sorma. Odaklan ve bitir.

Yanıt:"""

            response = await self.question_agent.llm_service.generate_response(
                prompt=message_text,
                system_message=SYSTEM_PROMPT,
                temperature=0.7,
                max_tokens=250
            )
            
            return response.strip()
            
        except Exception as e:
            self.logger.error(f"Generate error: {e}")
            # Final safety fallback using the deterministic Agent 1 logic
            try:
                agent_result = self.question_agent._fallback_question_selection(
                    profile, 
                    profile.get_unanswered_categories()
                )
                if agent_result.get("question"):
                    return agent_result["question"]
            except:
                pass
            return "Pardon, bir aksaklık oldu. Devam edelim mi?"
    
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
                "notlar": profile.lifestyle_notes,
            },
            "konut_tercihleri": {
                "hedef_sehir": (profile.location.city if profile.location else None) or profile.current_city or profile.hometown,
                "hedef_ilce": profile.location.district if (profile.location and hasattr(profile.location, 'district')) else None,
                "oda_sayisi": profile.property_preferences.min_rooms if profile.property_preferences else None,
                "ev_tipi": (profile.property_preferences.property_type.value if profile.property_preferences.property_type else None) if profile.property_preferences else None,
                "sosyal_alanlar": profile.social_amenities if profile.social_amenities else [],
                "satin_alma_amaci": profile.purchase_purpose,
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
                "ozet": structured.get("summary", ""),
                "tavsiyeler": structured.get("recommendations", []),
                "dikkat_noktalari": structured.get("key_considerations", []),
                "yasam_tarzi_notlari": structured.get("lifestyle_insights", []) if structured else [],
            },
            "status": "PROFIL_TAMAMLANDI_EMLAKCIYA_GONDERILDI"
        }
    
    def _save_crm_report_to_file(self, crm_report: dict, profile: UserProfile) -> str:
        """Save CRM report to a JSON file for the real estate agent."""
        try:
            # Create reports directory if it doesn't exist
            # Use absolute path mapped to Docker volume
            reports_dir = Path("/app/customer_reports")
            reports_dir.mkdir(exist_ok=True)
            
            # Generate filename with customer name and timestamp
            customer_name = (profile.name or "unknown").lower().replace(" ", "_")
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"{customer_name}_{timestamp}.json"
            filepath = reports_dir / filename
            
            # Write report to file (JSON)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(crm_report, f, ensure_ascii=False, indent=2)
            
            self.logger.info(f"CRM report (JSON) saved to: {filepath}")
            
            # Write report to file (PDF)
            pdf_filename = f"{customer_name}_{timestamp}.pdf"
            pdf_filepath = reports_dir / pdf_filename
            
            pdf_gen = PDFReportGenerator()
            pdf_gen.generate(crm_report, pdf_filepath)
            
            return str(pdf_filepath)
            
        except Exception as e:
            self.logger.error(f"Failed to save CRM report: {e}", exc_info=True)
            return "DOSYA_KAYIT_HATASI"
