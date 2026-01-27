"""Process user message use case - Main orchestration logic."""

from typing import Optional
from uuid import UUID
import re

from application.agents import QuestionAgent, ValidationAgent, AnalysisAgent
from domain.entities import UserProfile, Conversation
from domain.repositories import IUserRepository, IConversationRepository
from domain.enums import QuestionCategory
from infrastructure.config import get_logger


class ProcessUserMessageUseCase:
    """
    Use case for processing user messages and orchestrating agent workflow.
    """
    
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
            self.logger.info(f"Got conversation: {conversation.id}")
            
            # Add user message to conversation
            conversation.add_user_message(user_message)
            await self.conversation_repo.update(conversation)
            
            # CRITICAL FIX: If name is not set, this message IS the name
            if not user_profile.name and user_message.strip():
                name = user_message.strip()
                if len(name) < 100:
                    user_profile.name = name
                    user_profile.answered_categories.add(QuestionCategory.NAME)
                    self.logger.info(f"Captured name directly: {name}")
            else:
                # Try to extract other information
                try:
                    await self._update_profile_from_message(user_profile, user_message)
                except Exception as extract_error:
                    self.logger.warning(f"Extraction error (non-fatal): {extract_error}")
            
            # Save profile
            await self.user_repo.update(user_profile)
            self.logger.info(f"Profile updated, answered categories: {[c.value for c in user_profile.answered_categories]}")
            
            # Skip complex validation - just check basic completeness
            is_ready = user_profile.is_complete()
            self.logger.info(f"Profile complete check: {is_ready}")
            
            if is_ready:
                # Profile complete - generate simple response for now
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
                # Profile incomplete - ask next question
                self.logger.info("Profile incomplete, getting next question")
                
                try:
                    question_result = await self.question_agent.execute(user_profile, conversation)
                    next_question = question_result.get("question")
                    category = question_result.get("category")
                except Exception as q_error:
                    self.logger.error(f"Question agent error: {q_error}")
                    # Fallback question
                    if not user_profile.name:
                        next_question = "İsminizi öğrenebilir miyim?"
                        category = "name"
                    elif not user_profile.budget:
                        next_question = f"Teşekkürler {user_profile.name}! Ev almak için bütçeniz ne kadar?"
                        category = "budget"
                    else:
                        next_question = f"{user_profile.name}, hangi şehirde ev arıyorsunuz?"
                        category = "location"
                
                if next_question:
                    conversation.add_assistant_message(next_question)
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
            # Return a graceful error response instead of raising
            return {
                "response": "Bir sorun oluştu ama devam edebiliriz. Lütfen tekrar deneyin.",
                "type": "error",
                "is_complete": False,
            }
    
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
            # Create a temporary profile
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
        """Update user profile based on message content using simple pattern matching."""
        message_lower = message.lower()
        
        # Email extraction
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', message)
        if email_match:
            user_profile.email = email_match.group()
            user_profile.answered_categories.add(QuestionCategory.EMAIL)
            self.logger.info(f"Extracted email: {user_profile.email}")
        
        # Phone extraction (Turkish format)
        phone_match = re.search(r'(?:0|\+90)?[- ]?5\d{2}[- ]?\d{3}[- ]?\d{2}[- ]?\d{2}', message)
        if phone_match:
            user_profile.phone = phone_match.group()
            user_profile.answered_categories.add(QuestionCategory.PHONE)
            self.logger.info(f"Extracted phone: {user_profile.phone}")
        
        # Marital status
        if any(word in message_lower for word in ['evliyim', 'evli']):
            user_profile.marital_status = 'Evli'
            user_profile.answered_categories.add(QuestionCategory.MARITAL_STATUS)
        elif any(word in message_lower for word in ['bekarım', 'bekar']):
            user_profile.marital_status = 'Bekar'
            user_profile.answered_categories.add(QuestionCategory.MARITAL_STATUS)
        
        # Children
        if any(word in message_lower for word in ['çocuğum var', 'çocuklarım']):
            user_profile.has_children = True
            user_profile.answered_categories.add(QuestionCategory.CHILDREN)
        elif 'çocuğum yok' in message_lower:
            user_profile.has_children = False
            user_profile.answered_categories.add(QuestionCategory.CHILDREN)
        
        # Budget extraction
        budget_numbers = re.findall(r'(\d{1,3}(?:[.,]\d{3})*)', message)
        if budget_numbers:
            numbers = []
            for match in budget_numbers:
                num_str = match.replace('.', '').replace(',', '')
                try:
                    num = int(num_str)
                    if num > 10000:
                        numbers.append(num)
                except:
                    pass
            
            if numbers:
                from domain.value_objects import Budget
                min_amt = min(numbers)
                max_amt = max(numbers) if len(numbers) > 1 else int(min_amt * 1.2)
                user_profile.budget = Budget(min_amount=min_amt, max_amount=max_amt)
                user_profile.answered_categories.add(QuestionCategory.BUDGET)
                self.logger.info(f"Extracted budget: {min_amt} - {max_amt}")
        
        # Location extraction
        cities = ['istanbul', 'ankara', 'izmir', 'bursa', 'antalya', 'adana', 
                 'gaziantep', 'konya', 'mersin', 'kayseri', 'eskişehir', 
                 'samsun', 'denizli', 'trabzon', 'malatya', 'kocaeli']
        
        for city in cities:
            if city in message_lower:
                from domain.value_objects import Location
                user_profile.location = Location(city=city.title(), district=None, country="Turkey")
                user_profile.answered_categories.add(QuestionCategory.LOCATION)
                self.logger.info(f"Extracted location: {city}")
                break
        
        # Property type
        if 'daire' in message_lower or 'apartman' in message_lower:
            from domain.value_objects import PropertyPreferences
            from domain.enums import PropertyType
            user_profile.property_preferences = PropertyPreferences(property_type=PropertyType.APARTMENT)
            user_profile.answered_categories.add(QuestionCategory.PROPERTY_TYPE)
        elif 'villa' in message_lower:
            from domain.value_objects import PropertyPreferences
            from domain.enums import PropertyType
            user_profile.property_preferences = PropertyPreferences(property_type=PropertyType.VILLA)
            user_profile.answered_categories.add(QuestionCategory.PROPERTY_TYPE)
        elif 'müstakil' in message_lower:
            from domain.value_objects import PropertyPreferences
            from domain.enums import PropertyType
            user_profile.property_preferences = PropertyPreferences(property_type=PropertyType.DETACHED_HOUSE)
            user_profile.answered_categories.add(QuestionCategory.PROPERTY_TYPE)
        
        # Rooms
        room_match = re.search(r'(\d+)\s*(?:\+\s*(\d+))?\s*(?:oda|room)', message_lower)
        if room_match:
            user_profile.answered_categories.add(QuestionCategory.ROOMS)
        
        # Family size
        family_match = re.search(r'(\d+)\s*(?:kişi|kisilik|kişilik)', message_lower)
        if family_match:
            user_profile.family_size = int(family_match.group(1))
            user_profile.answered_categories.add(QuestionCategory.FAMILY_SIZE)
    
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
