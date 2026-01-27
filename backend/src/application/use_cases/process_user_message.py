"""Process user message use case - Natural AI conversation with memory."""

from typing import Optional
from uuid import UUID
import re

from application.agents import QuestionAgent, ValidationAgent, AnalysisAgent
from domain.entities import UserProfile, Conversation
from domain.repositories import IUserRepository, IConversationRepository
from domain.enums import QuestionCategory
from infrastructure.config import get_logger


# Turkish greetings to detect
GREETINGS = [
    'merhaba', 'selam', 'selamlar', 'mrb', 'slm', 'hey', 'hi', 'hello',
    'günaydın', 'iyi günler', 'iyi akşamlar', 'naber', 'nasılsın',
    'sa', 'selamun aleyküm', 'as', 'merhabalar', 'nbr'
]

# Turkish cities
TURKISH_CITIES = [
    'istanbul', 'ankara', 'izmir', 'bursa', 'antalya', 'adana', 
    'gaziantep', 'konya', 'mersin', 'kayseri', 'eskişehir', 
    'samsun', 'denizli', 'trabzon', 'malatya', 'kocaeli',
    'diyarbakır', 'şanlıurfa', 'hatay', 'manisa', 'kahramanmaraş',
    'van', 'aydın', 'balıkesir', 'tekirdağ', 'sakarya', 'muğla'
]

# System prompt for natural conversation
SYSTEM_PROMPT = """Sen profesyonel ama samimi bir AI emlak danışmanısın.

TEMEL PRENSİPLER:
- Kullanıcının ismini mutlaka al (hitap için zorunlu)
- İsim almadan emlak detaylarına girme
- Sohbet gibi ilerle, form doldurur gibi değil
- Aynı anda yalnızca 1 soru sor
- Daha önce cevaplanmış bir soruyu ASLA tekrar sorma
- Kullanıcı kısa cevap verirse bozulma, sohbeti toparla

YASAK DAVRANIŞLAR:
❌ Arka arkaya soru yağmuru
❌ "Şimdi şunu soruyorum" gibi robot cümleler
❌ "Teşekkürler X!" kalıp cümlesi sürekli tekrar
❌ Kullanıcıyı form dolduruyormuş gibi hissettirmek

TON:
- Samimi ama profesyonel
- İnsan gibi, doğal
- Gerektiğinde empatik
- ASLA laubali değil
- Türkçe, kısa ve öz"""


class ProcessUserMessageUseCase:
    """Use case for processing user messages with natural LLM conversation."""
    
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
        """Process user message with natural conversation."""
        try:
            self.logger.info(f"Processing: {user_message[:50]}")
            
            # Get or create profile and conversation
            user_profile = await self._get_or_create_user_profile(session_id)
            conversation = await self._get_or_create_conversation(user_profile.id)
            
            # Add user message
            conversation.add_user_message(user_message)
            await self.conversation_repo.update(conversation)
            
            message_lower = user_message.lower().strip()
            
            # Check if greeting
            is_greeting = any(g == message_lower or message_lower.startswith(g + ' ') for g in GREETINGS)
            
            # Get last question category
            last_category = self._get_last_question_category(conversation)
            
            # Process based on context
            if is_greeting:
                # Just a greeting, don't save as name
                pass
            elif last_category == "name" or (not user_profile.name and not is_greeting):
                # This should be the name
                user_profile.name = user_message.strip()
                user_profile.answered_categories.add(QuestionCategory.NAME)
                self.logger.info(f"Saved name: {user_profile.name}")
            elif last_category:
                # Process answer for the category
                self._process_answer(user_profile, user_message, last_category)
            else:
                # Try to extract info
                self._extract_info(user_profile, user_message)
            
            # Save profile
            await self.user_repo.update(user_profile)
            
            # Generate natural response
            response_text = await self._generate_response(
                user_profile, 
                conversation, 
                user_message,
                is_greeting
            )
            
            # Get next category for metadata
            next_category = self._get_next_category(user_profile)
            
            # Save response
            conversation.add_assistant_message(
                response_text,
                metadata={"category": next_category}
            )
            await self.conversation_repo.update(conversation)
            
            # Check completion
            is_ready = user_profile.is_complete()
            
            return {
                "response": response_text,
                "type": "analysis" if is_ready else "question",
                "is_complete": is_ready,
                "category": next_category,
            }
            
        except Exception as e:
            self.logger.error(f"Error: {str(e)}", exc_info=True)
            return {
                "response": "Pardon, küçük bir aksaklık oldu. Devam edelim mi?",
                "type": "error",
                "is_complete": False,
            }
    
    async def _generate_response(
        self, 
        user_profile: UserProfile, 
        conversation: Conversation,
        user_message: str,
        is_greeting: bool
    ) -> str:
        """Generate natural response using LLM."""
        try:
            # Build context
            history = self._format_history(conversation)
            memory = self._format_memory(user_profile)
            next_needed = self._get_next_needed_info(user_profile)
            
            prompt = f"""HAFIZADA OLAN BİLGİLER:
{memory}

SON SOHBET:
{history}

KULLANICININ SON MESAJI: "{user_message}"

SONRAKİ TOPLANACAK BİLGİ: {next_needed}

GÖREV:
1. Kullanıcının mesajına uygun, doğal bir yanıt ver
2. Eğer selamlaştıysa, selamla ve ismini sor
3. Eğer isim aldıysan, memnun ol ve sonraki şeyi sor (şehir gibi)
4. Asla robot gibi konuşma
5. 1-2 cümle max, kısa ve öz
6. Hafızadaki bilgileri tekrar sorma

YANITINI YAZ (sadece yanıt metni):"""

            response = await self.question_agent.llm_service.generate_response(
                prompt=prompt,
                system_message=SYSTEM_PROMPT,
                temperature=0.8,
                max_tokens=100
            )
            
            return response.strip()
            
        except Exception as e:
            self.logger.error(f"LLM error: {e}")
            return self._fallback_response(user_profile, is_greeting)
    
    def _fallback_response(self, user_profile: UserProfile, is_greeting: bool) -> str:
        """Fallback if LLM fails."""
        if is_greeting:
            return "Merhaba! 😊 Hoş geldiniz. Size nasıl hitap edebilirim?"
        
        if not user_profile.name:
            return "Size nasıl hitap edebilirim?"
        
        name = user_profile.name
        
        if QuestionCategory.EMAIL not in user_profile.answered_categories:
            return f"Memnun oldum {name}! Sizinle iletişim için mail adresinizi alabilir miyim?"
        
        if QuestionCategory.HOMETOWN not in user_profile.answered_categories:
            return f"Peki {name}, şu anda hangi şehirde yaşıyorsunuz?"
        
        if QuestionCategory.BUDGET not in user_profile.answered_categories:
            return "Ev için düşündüğünüz bir bütçe aralığı var mı?"
        
        if QuestionCategory.LOCATION not in user_profile.answered_categories:
            return "Hangi şehirde ev arıyorsunuz?"
        
        return f"Devam edelim {name}, başka bir şey sormak ister misiniz?"
    
    def _format_history(self, conversation: Conversation) -> str:
        """Format recent conversation."""
        recent = conversation.get_recent_messages(6)
        if not recent:
            return "Yeni sohbet başladı"
        
        lines = []
        for msg in recent:
            role = "Kullanıcı" if msg.role.value == "user" else "Asistan"
            lines.append(f"{role}: {msg.content}")
        
        return "\n".join(lines)
    
    def _format_memory(self, user_profile: UserProfile) -> str:
        """Format user memory/profile."""
        parts = []
        
        if user_profile.name:
            parts.append(f"✓ İsim: {user_profile.name}")
        else:
            parts.append("✗ İsim: Bilinmiyor (SORMALISIN)")
        
        if user_profile.email:
            parts.append(f"✓ E-posta: {user_profile.email}")
        
        if user_profile.hometown:
            parts.append(f"✓ Yaşadığı şehir: {user_profile.hometown}")
        
        if user_profile.profession:
            parts.append(f"✓ Meslek: {user_profile.profession}")
        
        if user_profile.budget:
            parts.append(f"✓ Bütçe: {user_profile.budget.min_amount:,} - {user_profile.budget.max_amount:,} TL")
        
        if user_profile.location:
            parts.append(f"✓ Aradığı konum: {user_profile.location.city}")
        
        if user_profile.property_preferences:
            parts.append(f"✓ Ev tipi: {user_profile.property_preferences.property_type.value}")
        
        if user_profile.family_size:
            parts.append(f"✓ Aile: {user_profile.family_size} kişi")
        
        return "\n".join(parts) if parts else "Henüz bilgi yok"
    
    def _get_next_needed_info(self, user_profile: UserProfile) -> str:
        """Describe next info to collect."""
        if not user_profile.name:
            return "İSİM (zorunlu - hitap için)"
        
        needs = []
        
        if QuestionCategory.EMAIL not in user_profile.answered_categories:
            needs.append("E-posta")
        if QuestionCategory.HOMETOWN not in user_profile.answered_categories:
            needs.append("Şu an yaşadığı şehir")
        if QuestionCategory.PROFESSION not in user_profile.answered_categories:
            needs.append("Meslek/yaşam durumu")
        if QuestionCategory.BUDGET not in user_profile.answered_categories:
            needs.append("Bütçe")
        if QuestionCategory.LOCATION not in user_profile.answered_categories:
            needs.append("Ev aradığı şehir/ilçe")
        if QuestionCategory.PROPERTY_TYPE not in user_profile.answered_categories:
            needs.append("Ev tipi (daire/villa)")
        
        if not needs:
            return "Tüm bilgiler tamam, analiz yapılabilir"
        
        return needs[0]  # Return first needed
    
    def _get_next_category(self, user_profile: UserProfile) -> Optional[str]:
        """Get next category for metadata."""
        if not user_profile.name:
            return "name"
        
        priority = [
            QuestionCategory.EMAIL,
            QuestionCategory.HOMETOWN,
            QuestionCategory.PROFESSION,
            QuestionCategory.BUDGET,
            QuestionCategory.LOCATION,
            QuestionCategory.PROPERTY_TYPE,
            QuestionCategory.ROOMS,
            QuestionCategory.FAMILY_SIZE,
        ]
        
        for cat in priority:
            if cat not in user_profile.answered_categories:
                return cat.value
        
        return None
    
    def _get_last_question_category(self, conversation: Conversation) -> Optional[str]:
        """Get last asked category."""
        recent = conversation.get_recent_messages(2)
        for msg in reversed(recent):
            if msg.role.value == "assistant" and msg.metadata:
                return msg.metadata.get("category")
        return None
    
    def _process_answer(self, user_profile: UserProfile, message: str, category: str) -> None:
        """Process answer for specific category."""
        message_lower = message.lower().strip()
        
        if category == "name":
            if not any(g in message_lower for g in GREETINGS):
                user_profile.name = message.strip()
                user_profile.answered_categories.add(QuestionCategory.NAME)
        
        elif category == "email":
            email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', message)
            if email_match:
                user_profile.email = email_match.group()
                user_profile.answered_categories.add(QuestionCategory.EMAIL)
        
        elif category == "hometown":
            for city in TURKISH_CITIES:
                if city in message_lower:
                    user_profile.hometown = city.title()
                    user_profile.answered_categories.add(QuestionCategory.HOMETOWN)
                    return
            user_profile.hometown = message.strip().title()
            user_profile.answered_categories.add(QuestionCategory.HOMETOWN)
        
        elif category == "profession":
            user_profile.profession = message.strip()
            user_profile.answered_categories.add(QuestionCategory.PROFESSION)
        
        elif category == "budget":
            numbers = re.findall(r'(\d{1,3}(?:[.,]\d{3})*)', message)
            if numbers:
                parsed = []
                for n in numbers:
                    num_str = n.replace('.', '').replace(',', '')
                    try:
                        parsed.append(int(num_str))
                    except:
                        pass
                if parsed:
                    from domain.value_objects import Budget
                    min_amt = min(parsed)
                    max_amt = max(parsed) if len(parsed) > 1 else int(min_amt * 1.2)
                    user_profile.budget = Budget(min_amount=min_amt, max_amount=max_amt)
                    user_profile.answered_categories.add(QuestionCategory.BUDGET)
        
        elif category == "location":
            for city in TURKISH_CITIES:
                if city in message_lower:
                    from domain.value_objects import Location
                    user_profile.location = Location(city=city.title(), country="Turkey")
                    user_profile.answered_categories.add(QuestionCategory.LOCATION)
                    return
            from domain.value_objects import Location
            user_profile.location = Location(city=message.strip().title(), country="Turkey")
            user_profile.answered_categories.add(QuestionCategory.LOCATION)
        
        elif category == "property_type":
            from domain.value_objects import PropertyPreferences
            from domain.enums import PropertyType
            
            if 'daire' in message_lower:
                t = PropertyType.APARTMENT
            elif 'villa' in message_lower:
                t = PropertyType.VILLA
            elif 'müstakil' in message_lower:
                t = PropertyType.DETACHED_HOUSE
            else:
                t = PropertyType.APARTMENT
            
            user_profile.property_preferences = PropertyPreferences(property_type=t)
            user_profile.answered_categories.add(QuestionCategory.PROPERTY_TYPE)
        
        elif category == "rooms":
            match = re.search(r'(\d+)', message)
            if match:
                rooms = int(match.group(1))
                if user_profile.property_preferences:
                    user_profile.property_preferences.min_rooms = rooms
                user_profile.answered_categories.add(QuestionCategory.ROOMS)
        
        elif category == "family_size":
            match = re.search(r'(\d+)', message)
            if match:
                user_profile.family_size = int(match.group(1))
                user_profile.answered_categories.add(QuestionCategory.FAMILY_SIZE)
    
    def _extract_info(self, user_profile: UserProfile, message: str) -> None:
        """Extract any info from message."""
        # Email
        email = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', message)
        if email:
            user_profile.email = email.group()
            user_profile.answered_categories.add(QuestionCategory.EMAIL)
    
    async def _get_or_create_user_profile(self, session_id: str) -> UserProfile:
        try:
            profile = await self.user_repo.get_by_session_id(session_id)
            if profile is None:
                profile = UserProfile(session_id=session_id)
                profile = await self.user_repo.create(profile)
            return profile
        except Exception as e:
            self.logger.error(f"Profile error: {e}")
            return UserProfile(session_id=session_id)
    
    async def _get_or_create_conversation(self, user_profile_id: UUID) -> Conversation:
        try:
            conv = await self.conversation_repo.get_by_user_profile_id(user_profile_id)
            if conv is None:
                conv = Conversation(user_profile_id=user_profile_id)
                conv = await self.conversation_repo.create(conv)
            return conv
        except Exception as e:
            self.logger.error(f"Conv error: {e}")
            return Conversation(user_profile_id=user_profile_id)
