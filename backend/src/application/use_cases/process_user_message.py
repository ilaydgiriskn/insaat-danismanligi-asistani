"""Process user message - Free-flow LLM conversation for real estate."""

from typing import Optional
from uuid import UUID
import re
import json

from application.agents import QuestionAgent, ValidationAgent, AnalysisAgent
from domain.entities import UserProfile, Conversation
from domain.repositories import IUserRepository, IConversationRepository
from domain.enums import QuestionCategory
from infrastructure.config import get_logger


GREETINGS = ['merhaba', 'selam', 'selamlar', 'mrb', 'slm', 'hey', 'hi', 'sa', 'merhabalar', 'naber']

SYSTEM_PROMPT = """Sen samimi, sıcak ve profesyonel bir emlak danışmanısın.

GÖREV:
Kullanıcıyla DOĞAL SOHBET ederek onu tanı ve ev ihtiyaçlarını anla.
Asla form doldurur gibi sorma, arkadaşça sohbet et.

SOHBET TARZI:
- Samimi ama profesyonel
- Kullanıcının cevaplarına BAĞLAMLI sorular sor
- Hobi, meslek, aile gibi konuları EV İHTİYACINA bağla
- Örnek: Spor yapıyorsa → spor salonuna yakınlık önemli mi?
- Örnek: Evcil hayvanı varsa → bahçeli/geniş ev lazım mı?
- Örnek: Çocukları varsa → okula yakınlık, güvenli site vs.

KURALLARI:
1. Her seferinde TEK SORU sor
2. Kısa ve doğal ol (1-2 cümle)
3. Aynı bilgiyi tekrar sorma
4. Robot cümleleri ("Teşekkürler X!") kullanma
5. Emoji kullanabilirsin ama abartma
6. Türkçe konuş

TOPLANACAK BİLGİLER (zamanla, sohbet içinde):
- İsim (zorunlu)
- Nereli/nerede yaşıyor
- Meslek
- Medeni durum, çocuk
- Hobi/ilgi alanları
- Bütçe
- Hangi şehirde ev arıyor
- Ev tipi tercihi
- Özel ihtiyaçlar (işe yakınlık, okul, spor salonu vs.)

AMA: Bunları sırayla sorma! Sohbetin doğal akışına göre sor."""


class ProcessUserMessageUseCase:
    """Natural conversation for real estate consultation."""
    
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
        """Process message with free-flow conversation."""
        try:
            # Get profile and conversation
            user_profile = await self._get_or_create_user_profile(session_id)
            conversation = await self._get_or_create_conversation(user_profile.id)
            
            # Add user message
            conversation.add_user_message(user_message)
            
            message_lower = user_message.lower().strip()
            is_greeting = message_lower in GREETINGS or any(message_lower.startswith(g) for g in GREETINGS)
            
            # Extract info from message using LLM
            if not is_greeting:
                await self._extract_info_with_llm(user_profile, conversation, user_message)
            
            # Save profile
            await self.user_repo.update(user_profile)
            await self.conversation_repo.update(conversation)
            
            # Generate natural response
            response = await self._generate_free_response(user_profile, conversation, is_greeting)
            
            # Save response
            conversation.add_assistant_message(response)
            await self.conversation_repo.update(conversation)
            
            # Check if enough info for analysis
            is_ready = self._has_enough_info(user_profile)
            
            return {
                "response": response,
                "type": "analysis" if is_ready else "question",
                "is_complete": is_ready,
                "category": None,
            }
            
        except Exception as e:
            self.logger.error(f"Error: {str(e)}", exc_info=True)
            return {
                "response": "Pardon, bir aksaklık oldu. Neyse, devam edelim 😊",
                "type": "error",
                "is_complete": False,
            }
    
    async def _extract_info_with_llm(
        self, 
        user_profile: UserProfile, 
        conversation: Conversation,
        message: str
    ) -> None:
        """Use LLM to extract information from user message."""
        try:
            history = self._get_history(conversation, 4)
            
            prompt = f"""Son sohbet:
{history}

Kullanıcının son mesajı: "{message}"

Bu mesajdan çıkarılabilecek bilgileri JSON olarak ver.
Sadece NET olarak söylenen bilgileri çıkar, tahmin yapma.
Bilgi yoksa boş bırak.

JSON formatı:
{{
    "name": "isim veya null",
    "email": "email veya null", 
    "city": "yaşadığı şehir veya null",
    "hometown": "memleket veya null",
    "profession": "meslek veya null",
    "marital_status": "evli/bekar veya null",
    "has_children": true/false veya null,
    "children_count": sayı veya null,
    "hobbies": ["hobi1", "hobi2"] veya null,
    "has_pets": true/false veya null,
    "pet_type": "kedi/köpek vs veya null",
    "budget_min": sayı veya null,
    "budget_max": sayı veya null,
    "target_city": "ev aradığı şehir veya null",
    "property_type": "daire/villa/müstakil veya null",
    "special_needs": ["spor salonuna yakın", "okula yakın" vs.] veya null
}}

Sadece JSON döndür:"""

            response = await self.question_agent.llm_service.generate_response(
                prompt=prompt,
                system_message="Bilgi çıkarma uzmanısın. Sadece NET söylenen bilgileri çıkar.",
                temperature=0.1,
                max_tokens=300
            )
            
            # Parse JSON
            try:
                # Clean response
                content = response.strip()
                if content.startswith("```"):
                    content = content.split("```")[1]
                    if content.startswith("json"):
                        content = content[4:]
                content = content.strip()
                
                data = json.loads(content)
                self._apply_extracted_data(user_profile, data)
                
            except json.JSONDecodeError:
                self.logger.warning(f"Could not parse LLM response: {response[:100]}")
                # Fallback: basic extraction
                self._basic_extraction(user_profile, message)
                
        except Exception as e:
            self.logger.error(f"Extraction error: {e}")
            self._basic_extraction(user_profile, message)
    
    def _apply_extracted_data(self, user_profile: UserProfile, data: dict) -> None:
        """Apply extracted data to user profile."""
        if data.get("name") and not user_profile.name:
            user_profile.name = data["name"]
            user_profile.answered_categories.add(QuestionCategory.NAME)
            self.logger.info(f"Extracted name: {data['name']}")
        
        if data.get("email") and not user_profile.email:
            user_profile.email = data["email"]
            user_profile.answered_categories.add(QuestionCategory.EMAIL)
        
        if data.get("city") and not user_profile.hometown:
            user_profile.hometown = data["city"]
            user_profile.answered_categories.add(QuestionCategory.HOMETOWN)
        
        if data.get("hometown") and not user_profile.hometown:
            user_profile.hometown = data["hometown"]
            user_profile.answered_categories.add(QuestionCategory.HOMETOWN)
        
        if data.get("profession") and not user_profile.profession:
            user_profile.profession = data["profession"]
            user_profile.answered_categories.add(QuestionCategory.PROFESSION)
        
        if data.get("marital_status") and not user_profile.marital_status:
            user_profile.marital_status = data["marital_status"]
            user_profile.answered_categories.add(QuestionCategory.MARITAL_STATUS)
        
        if data.get("has_children") is not None and user_profile.has_children is None:
            user_profile.has_children = data["has_children"]
            user_profile.answered_categories.add(QuestionCategory.CHILDREN)
        
        if data.get("hobbies") and not user_profile.hobbies:
            user_profile.hobbies = data["hobbies"]
            user_profile.answered_categories.add(QuestionCategory.HOBBIES)
        
        if data.get("budget_min") and not user_profile.budget:
            from domain.value_objects import Budget
            min_amt = data["budget_min"]
            max_amt = data.get("budget_max") or int(min_amt * 1.2)
            user_profile.budget = Budget(min_amount=min_amt, max_amount=max_amt)
            user_profile.answered_categories.add(QuestionCategory.BUDGET)
        
        if data.get("target_city") and not user_profile.location:
            from domain.value_objects import Location
            user_profile.location = Location(city=data["target_city"], country="Turkey")
            user_profile.answered_categories.add(QuestionCategory.LOCATION)
        
        if data.get("property_type") and not user_profile.property_preferences:
            from domain.value_objects import PropertyPreferences
            from domain.enums import PropertyType
            
            ptype = data["property_type"].lower()
            if "villa" in ptype:
                t = PropertyType.VILLA
            elif "müstakil" in ptype:
                t = PropertyType.DETACHED_HOUSE
            else:
                t = PropertyType.APARTMENT
            
            user_profile.property_preferences = PropertyPreferences(property_type=t)
            user_profile.answered_categories.add(QuestionCategory.PROPERTY_TYPE)
        
        if data.get("special_needs"):
            if not user_profile.lifestyle_notes:
                user_profile.lifestyle_notes = ", ".join(data["special_needs"])
            else:
                user_profile.lifestyle_notes += ", " + ", ".join(data["special_needs"])
    
    def _basic_extraction(self, user_profile: UserProfile, message: str) -> None:
        """Basic regex extraction as fallback."""
        # Email
        email = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', message)
        if email and not user_profile.email:
            user_profile.email = email.group()
            user_profile.answered_categories.add(QuestionCategory.EMAIL)
    
    async def _generate_free_response(
        self, 
        user_profile: UserProfile, 
        conversation: Conversation,
        is_greeting: bool
    ) -> str:
        """Generate free-flow contextual response."""
        try:
            history = self._get_history(conversation, 6)
            memory = self._format_memory(user_profile)
            
            prompt = f"""BİLİNEN BİLGİLER:
{memory}

SOHBET GEÇMİŞİ:
{history}

GÖREV:
Kullanıcıyla doğal sohbet et. Ev konusuna hemen atılma.
Kullanıcıyı tanı, hayatını anla, sonra ev ihtiyaçlarına bağla.

ÖNEMLİ:
- Kullanıcının son mesajına BAĞLAMLI cevap ver
- Eğer hobi/meslek/aile söylediyse, bunu ev ihtiyacına bağlayabilirsin
- Örnek: "Spor yapıyorum" → "Güzel! Spor salonu yakın olsun ister misin?"
- Örnek: "2 çocuğum var" → "Çocuklar için okula yakınlık önemli mi?"
- AMA çok direkt olma, sohbet gibi sor

İSİM YOKSA: Önce ismini sor
İSİM VARSA: Sohbete devam et, doğal sorular sor

Sadece yanıt metnini yaz (1-2 cümle max):"""

            response = await self.question_agent.llm_service.generate_response(
                prompt=prompt,
                system_message=SYSTEM_PROMPT,
                temperature=0.85,
                max_tokens=120
            )
            
            return response.strip()
            
        except Exception as e:
            self.logger.error(f"Response error: {e}")
            return self._fallback_response(user_profile, is_greeting)
    
    def _fallback_response(self, user_profile: UserProfile, is_greeting: bool) -> str:
        """Fallback if LLM fails."""
        if is_greeting or not user_profile.name:
            return "Merhaba! 😊 Size nasıl hitap edebilirim?"
        return f"Anladım {user_profile.name}! Devam edelim, biraz daha sohbet edelim."
    
    def _get_history(self, conversation: Conversation, count: int = 6) -> str:
        """Get formatted conversation history."""
        recent = conversation.get_recent_messages(count)
        if not recent:
            return "Yeni sohbet"
        
        lines = []
        for msg in recent:
            role = "Kullanıcı" if msg.role.value == "user" else "Sen"
            lines.append(f"{role}: {msg.content}")
        return "\n".join(lines)
    
    def _format_memory(self, user_profile: UserProfile) -> str:
        """Format what we know about user."""
        parts = []
        
        if user_profile.name:
            parts.append(f"İsim: {user_profile.name}")
        else:
            parts.append("İsim: BİLİNMİYOR (sor!)")
        
        if user_profile.email:
            parts.append(f"Email: {user_profile.email}")
        if user_profile.hometown:
            parts.append(f"Yaşadığı yer: {user_profile.hometown}")
        if user_profile.profession:
            parts.append(f"Meslek: {user_profile.profession}")
        if user_profile.marital_status:
            parts.append(f"Medeni durum: {user_profile.marital_status}")
        if user_profile.has_children:
            parts.append("Çocuğu var")
        if user_profile.hobbies:
            parts.append(f"Hobiler: {', '.join(user_profile.hobbies)}")
        if user_profile.budget:
            parts.append(f"Bütçe: {user_profile.budget.min_amount:,}-{user_profile.budget.max_amount:,} TL")
        if user_profile.location:
            parts.append(f"Ev aradığı yer: {user_profile.location.city}")
        if user_profile.property_preferences:
            parts.append(f"Ev tipi: {user_profile.property_preferences.property_type.value}")
        if user_profile.lifestyle_notes:
            parts.append(f"Özel ihtiyaçlar: {user_profile.lifestyle_notes}")
        
        return "\n".join(parts) if parts else "Henüz bilgi yok"
    
    def _has_enough_info(self, user_profile: UserProfile) -> bool:
        """Check if we have enough info for analysis."""
        return (
            user_profile.name is not None
            and user_profile.budget is not None
            and user_profile.location is not None
            and user_profile.property_preferences is not None
        )
    
    async def _get_or_create_user_profile(self, session_id: str) -> UserProfile:
        try:
            profile = await self.user_repo.get_by_session_id(session_id)
            if not profile:
                profile = UserProfile(session_id=session_id)
                profile = await self.user_repo.create(profile)
            return profile
        except:
            return UserProfile(session_id=session_id)
    
    async def _get_or_create_conversation(self, user_profile_id: UUID) -> Conversation:
        try:
            conv = await self.conversation_repo.get_by_user_profile_id(user_profile_id)
            if not conv:
                conv = Conversation(user_profile_id=user_profile_id)
                conv = await self.conversation_repo.create(conv)
            return conv
        except:
            return Conversation(user_profile_id=user_profile_id)
