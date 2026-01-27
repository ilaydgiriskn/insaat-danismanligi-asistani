"""Process user message use case - Main orchestration logic."""

from typing import Optional
from uuid import UUID
import re

from application.agents import QuestionAgent, ValidationAgent, AnalysisAgent
from domain.entities import UserProfile, Conversation
from domain.repositories import IUserRepository, IConversationRepository
from domain.enums import QuestionCategory
from infrastructure.config import get_logger


# Turkish cities list for extraction
TURKISH_CITIES = [
    'istanbul', 'ankara', 'izmir', 'bursa', 'antalya', 'adana', 
    'gaziantep', 'konya', 'mersin', 'kayseri', 'eskişehir', 
    'samsun', 'denizli', 'trabzon', 'malatya', 'kocaeli',
    'diyarbakır', 'şanlıurfa', 'hatay', 'manisa', 'kahramanmaraş',
    'van', 'aydın', 'balıkesir', 'tekirdağ', 'sakarya', 'muğla',
    'erzurum', 'elazığ', 'batman', 'mardin', 'tokat', 'sivas',
    'ordu', 'rize', 'artvin', 'düzce', 'bolu', 'zonguldak',
    'edirne', 'kırklareli', 'çanakkale', 'afyon', 'isparta', 'burdur'
]


class ProcessUserMessageUseCase:
    """Use case for processing user messages and orchestrating agent workflow."""
    
    def __init__(
        self,
        user_repository: IUserRepository,
        conversation_repository: IConversationRepository,
        question_agent: QuestionAgent,
        validation_agent: ValidationAgent,
        analysis_agent: AnalysisAgent,
    ):
        """Initialize use case with dependencies."""
        self.user_repo = user_repository
        self.conversation_repo = conversation_repository
        self.question_agent = question_agent
        self.validation_agent = validation_agent
        self.analysis_agent = analysis_agent
        self.logger = get_logger(self.__class__.__name__)
    
    async def execute(
        self,
        session_id: str,
        user_message: str,
    ) -> dict:
        """Process user message and return appropriate response."""
        try:
            self.logger.info(f"Processing message for session: {session_id}")
            
            # Get or create user profile
            user_profile = await self._get_or_create_user_profile(session_id)
            self.logger.info(f"Got user profile: {user_profile.id}, name: {user_profile.name}")
            
            # Get or create conversation
            conversation = await self._get_or_create_conversation(user_profile.id)
            
            # Add user message to conversation
            conversation.add_user_message(user_message)
            await self.conversation_repo.update(conversation)
            
            # Determine what the last question was asking for
            last_category = self._get_last_question_category(conversation)
            self.logger.info(f"Last question category: {last_category}")
            
            # CRITICAL FIX: If name is not set, this message IS the name
            if not user_profile.name and user_message.strip():
                name = user_message.strip()
                if len(name) < 100:
                    user_profile.name = name
                    user_profile.answered_categories.add(QuestionCategory.NAME)
                    self.logger.info(f"Captured name directly: {name}")
            elif last_category:
                # Process answer based on what was asked
                self._process_answer_for_category(user_profile, user_message, last_category)
            else:
                # Try generic extraction
                await self._update_profile_from_message(user_profile, user_message)
            
            # Save profile
            await self.user_repo.update(user_profile)
            self.logger.info(f"Profile updated, answered: {[c.value for c in user_profile.answered_categories]}")
            
            # Check if profile is complete
            is_ready = user_profile.is_complete()
            
            if is_ready:
                self.logger.info("Profile complete, generating analysis")
                try:
                    analysis = await self.analysis_agent.execute(user_profile)
                    response_message = self._format_analysis_response(analysis)
                except Exception as analysis_error:
                    self.logger.error(f"Analysis error: {analysis_error}")
                    response_message = f"Teşekkürler {user_profile.name}! Bilgilerinizi aldım. Size uygun emlak önerileri hazırlıyorum."
                
                conversation.add_assistant_message(response_message)
                await self.conversation_repo.update(conversation)
                
                return {
                    "response": response_message,
                    "type": "analysis",
                    "is_complete": True,
                }
            else:
                self.logger.info("Profile incomplete, getting next question")
                try:
                    question_result = await self.question_agent.execute(user_profile, conversation)
                    next_question = question_result.get("question")
                    category = question_result.get("category")
                except Exception as q_error:
                    self.logger.error(f"Question agent error: {q_error}")
                    next_question = "Devam edelim! Başka bilgi paylaşmak ister misiniz?"
                    category = None
                
                if next_question:
                    conversation.add_assistant_message(
                        next_question,
                        metadata={"category": category}
                    )
                    await self.conversation_repo.update(conversation)
                    
                    return {
                        "response": next_question,
                        "type": "question",
                        "is_complete": False,
                        "category": category,
                    }
                else:
                    message = "Bilgilerinizi işliyorum..."
                    conversation.add_assistant_message(message)
                    await self.conversation_repo.update(conversation)
                    
                    return {
                        "response": message,
                        "type": "processing",
                        "is_complete": False,
                    }
                    
        except Exception as e:
            self.logger.error(f"Error processing message: {str(e)}", exc_info=True)
            return {
                "response": "Bir sorun oluştu ama devam edebiliriz. Lütfen tekrar deneyin.",
                "type": "error",
                "is_complete": False,
            }
    
    def _get_last_question_category(self, conversation: Conversation) -> Optional[str]:
        """Get the category of the last assistant question."""
        recent = conversation.get_recent_messages(2)
        for msg in reversed(recent):
            if msg.role.value == "assistant" and msg.metadata:
                return msg.metadata.get("category")
        return None
    
    def _process_answer_for_category(
        self, 
        user_profile: UserProfile, 
        message: str, 
        category: str
    ) -> None:
        """Process user's answer based on what category was being asked."""
        message_lower = message.lower().strip()
        
        if category == "email":
            email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', message)
            if email_match:
                user_profile.email = email_match.group()
                user_profile.answered_categories.add(QuestionCategory.EMAIL)
                self.logger.info(f"Saved email: {user_profile.email}")
        
        elif category == "phone":
            phone_match = re.search(r'(?:0|\+90)?[- ]?5\d{2}[- ]?\d{3}[- ]?\d{2}[- ]?\d{2}', message)
            if phone_match:
                user_profile.phone = phone_match.group()
                user_profile.answered_categories.add(QuestionCategory.PHONE)
        
        elif category == "hometown":
            # Check if message is a city name or contains city info
            for city in TURKISH_CITIES:
                if city in message_lower or message_lower == city:
                    user_profile.hometown = city.title()
                    user_profile.answered_categories.add(QuestionCategory.HOMETOWN)
                    self.logger.info(f"Saved hometown: {user_profile.hometown}")
                    return
            # If no city found, just save what they said
            if len(message) < 100:
                user_profile.hometown = message.strip().title()
                user_profile.answered_categories.add(QuestionCategory.HOMETOWN)
                self.logger.info(f"Saved hometown (raw): {user_profile.hometown}")
        
        elif category == "profession":
            if len(message) < 200:
                user_profile.profession = message.strip()
                user_profile.answered_categories.add(QuestionCategory.PROFESSION)
                self.logger.info(f"Saved profession: {user_profile.profession}")
        
        elif category == "marital_status":
            if any(w in message_lower for w in ['evli', 'evliyim']):
                user_profile.marital_status = "Evli"
            elif any(w in message_lower for w in ['bekar', 'bekarım']):
                user_profile.marital_status = "Bekar"
            else:
                user_profile.marital_status = message.strip()
            user_profile.answered_categories.add(QuestionCategory.MARITAL_STATUS)
        
        elif category == "children":
            if any(w in message_lower for w in ['var', 'evet']):
                user_profile.has_children = True
            elif any(w in message_lower for w in ['yok', 'hayır']):
                user_profile.has_children = False
            user_profile.answered_categories.add(QuestionCategory.CHILDREN)
        
        elif category == "salary":
            user_profile.estimated_salary = message.strip()
            user_profile.answered_categories.add(QuestionCategory.SALARY)
        
        elif category == "hobbies":
            user_profile.hobbies = [h.strip() for h in message.split(',')]
            user_profile.answered_categories.add(QuestionCategory.HOBBIES)
        
        elif category == "pets":
            user_profile.answered_categories.add(QuestionCategory.PETS)
        
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
                    self.logger.info(f"Saved budget: {min_amt} - {max_amt}")
        
        elif category == "location":
            for city in TURKISH_CITIES:
                if city in message_lower:
                    from domain.value_objects import Location
                    user_profile.location = Location(city=city.title(), country="Turkey")
                    user_profile.answered_categories.add(QuestionCategory.LOCATION)
                    self.logger.info(f"Saved location: {city}")
                    return
            # If no city found, save as-is
            from domain.value_objects import Location
            user_profile.location = Location(city=message.strip().title(), country="Turkey")
            user_profile.answered_categories.add(QuestionCategory.LOCATION)
        
        elif category == "property_type":
            from domain.value_objects import PropertyPreferences
            from domain.enums import PropertyType
            
            if 'daire' in message_lower or 'apartman' in message_lower:
                prop_type = PropertyType.APARTMENT
            elif 'villa' in message_lower:
                prop_type = PropertyType.VILLA
            elif 'müstakil' in message_lower:
                prop_type = PropertyType.DETACHED_HOUSE
            else:
                prop_type = PropertyType.APARTMENT  # Default
            
            user_profile.property_preferences = PropertyPreferences(property_type=prop_type)
            user_profile.answered_categories.add(QuestionCategory.PROPERTY_TYPE)
        
        elif category == "rooms":
            room_match = re.search(r'(\d+)\s*(?:\+\s*(\d+))?', message)
            if room_match:
                rooms = int(room_match.group(1))
                if room_match.group(2):
                    rooms += int(room_match.group(2))
                if user_profile.property_preferences:
                    user_profile.property_preferences.min_rooms = rooms
                    user_profile.property_preferences.max_rooms = rooms
                user_profile.answered_categories.add(QuestionCategory.ROOMS)
        
        elif category == "family_size":
            family_match = re.search(r'(\d+)', message)
            if family_match:
                user_profile.family_size = int(family_match.group(1))
                user_profile.answered_categories.add(QuestionCategory.FAMILY_SIZE)
    
    async def _get_or_create_user_profile(self, session_id: str) -> UserProfile:
        """Get existing user profile or create new one."""
        try:
            user_profile = await self.user_repo.get_by_session_id(session_id)
            if user_profile is None:
                user_profile = UserProfile(session_id=session_id)
                user_profile = await self.user_repo.create(user_profile)
                self.logger.info(f"Created new user profile: {user_profile.id}")
            return user_profile
        except Exception as e:
            self.logger.error(f"Error getting/creating user profile: {e}")
            return UserProfile(session_id=session_id)
    
    async def _get_or_create_conversation(self, user_profile_id: UUID) -> Conversation:
        """Get active conversation or create new one."""
        try:
            conversation = await self.conversation_repo.get_by_user_profile_id(user_profile_id)
            if conversation is None:
                conversation = Conversation(user_profile_id=user_profile_id)
                conversation = await self.conversation_repo.create(conversation)
                self.logger.info(f"Created new conversation: {conversation.id}")
            return conversation
        except Exception as e:
            self.logger.error(f"Error getting/creating conversation: {e}")
            return Conversation(user_profile_id=user_profile_id)
    
    async def _update_profile_from_message(self, user_profile: UserProfile, message: str) -> None:
        """Generic extraction when no specific category is expected."""
        message_lower = message.lower()
        
        # Email
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', message)
        if email_match:
            user_profile.email = email_match.group()
            user_profile.answered_categories.add(QuestionCategory.EMAIL)
        
        # Phone
        phone_match = re.search(r'(?:0|\+90)?[- ]?5\d{2}[- ]?\d{3}[- ]?\d{2}[- ]?\d{2}', message)
        if phone_match:
            user_profile.phone = phone_match.group()
            user_profile.answered_categories.add(QuestionCategory.PHONE)
    
    def _format_analysis_response(self, analysis: dict) -> str:
        """Format analysis results into user-friendly message."""
        parts = []
        
        if analysis.get("summary"):
            parts.append(f"📊 **Analiz Özeti**\n{analysis['summary']}\n")
        
        if analysis.get("recommendations"):
            parts.append("🏠 **Öneriler:**")
            for i, rec in enumerate(analysis["recommendations"][:5], 1):
                parts.append(f"{i}. {rec}")
        
        if analysis.get("budget_analysis"):
            parts.append(f"\n💰 **Bütçe Analizi:**\n{analysis['budget_analysis']}")
        
        return "\n".join(parts) if parts else "Analiz hazırlandı!"
