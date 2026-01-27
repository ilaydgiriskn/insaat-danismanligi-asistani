"""Process user message use case - Main orchestration logic."""

from typing import Optional
from uuid import UUID

from application.agents import QuestionAgent, ValidationAgent, AnalysisAgent
from domain.entities import UserProfile, Conversation
from domain.repositories import IUserRepository, IConversationRepository
from domain.enums import QuestionCategory
from infrastructure.config import get_logger


class ProcessUserMessageUseCase:
    """
    Use case for processing user messages and orchestrating agent workflow.
    
    This is the main entry point for handling user interactions.
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
        """
        Process user message and return appropriate response.
        
        Args:
            session_id: User session identifier
            user_message: User's message content
            
        Returns:
            Dict with response and metadata
        """
        try:
            self.logger.info(f"Processing message for session: {session_id}")
            
            # Get or create user profile
            user_profile = await self._get_or_create_user_profile(session_id)
            
            # Get or create conversation
            conversation = await self._get_or_create_conversation(user_profile.id)
            
            # Add user message to conversation
            conversation.add_user_message(user_message)
            await self.conversation_repo.update(conversation)
            
            # Update user profile based on message
            await self._update_profile_from_message(user_profile, user_message)
            await self.user_repo.update(user_profile)
            
            # Validate profile
            validation_result = await self.validation_agent.execute(user_profile)
            
            if validation_result["is_ready_for_analysis"]:
                # Profile complete - generate analysis
                self.logger.info("Profile complete, generating analysis")
                
                analysis = await self.analysis_agent.execute(user_profile)
                
                response_message = self._format_analysis_response(analysis)
                conversation.add_assistant_message(
                    response_message,
                    metadata={"agent": "analysis", "type": "recommendations"}
                )
                await self.conversation_repo.update(conversation)
                
                return {
                    "response": response_message,
                    "type": "analysis",
                    "is_complete": True,
                    "analysis": analysis,
                }
            else:
                # Profile incomplete - ask next question
                self.logger.info("Profile incomplete, asking next question")
                
                question_result = await self.question_agent.execute(
                    user_profile,
                    conversation
                )
                
                if question_result["question"]:
                    conversation.add_assistant_message(
                        question_result["question"],
                        metadata={
                            "agent": "question",
                            "category": question_result["category"]
                        }
                    )
                    await self.conversation_repo.update(conversation)
                    
                    return {
                        "response": question_result["question"],
                        "type": "question",
                        "is_complete": False,
                        "category": question_result["category"],
                    }
                else:
                    # No more questions but not ready for analysis
                    message = "Bilgilerinizi gözden geçiriyorum..."
                    conversation.add_assistant_message(message)
                    await self.conversation_repo.update(conversation)
                    
                    return {
                        "response": message,
                        "type": "processing",
                        "is_complete": False,
                    }
                    
        except Exception as e:
            self.logger.error(f"Error processing message: {str(e)}", exc_info=True)
            raise
    
    async def _get_or_create_user_profile(self, session_id: str) -> UserProfile:
        """Get existing user profile or create new one."""
        user_profile = await self.user_repo.get_by_session_id(session_id)
        
        if user_profile is None:
            user_profile = UserProfile(session_id=session_id)
            user_profile = await self.user_repo.create(user_profile)
            self.logger.info(f"Created new user profile: {user_profile.id}")
        
        return user_profile
    
    async def _get_or_create_conversation(
        self,
        user_profile_id: UUID
    ) -> Conversation:
        """Get active conversation or create new one."""
        conversation = await self.conversation_repo.get_by_user_profile_id(
            user_profile_id
        )
        
        if conversation is None:
            conversation = Conversation(user_profile_id=user_profile_id)
            conversation = await self.conversation_repo.create(conversation)
            self.logger.info(f"Created new conversation: {conversation.id}")
        
        return conversation
    
    async def _update_profile_from_message(
        self,
        user_profile: UserProfile,
        message: str
    ) -> None:
        """
        Update user profile based on message content using LLM extraction.
        """
        try:
            # Import here to avoid circular dependency
            from infrastructure.llm.information_extractor import InformationExtractor
            from infrastructure.llm import LangChainService
            
            # Create extractor
            llm_service = LangChainService()
            extractor = InformationExtractor(llm_service)
            
            # Get conversation history for context
            conversation = await self.conversation_repo.get_by_user_profile_id(user_profile.id)
            history = ""
            if conversation:
                recent = conversation.get_recent_messages(5)
                history = "\n".join([f"{msg.role.value}: {msg.content}" for msg in recent])
            
            # Extract information
            extracted = await extractor.extract_profile_info(message, history)
            
            # Update profile with extracted information
            if extracted.get("name"):
                user_profile.update_name(extracted["name"])
            
            if extracted.get("email"):
                user_profile.email = extracted["email"]
                user_profile.answered_categories.add(QuestionCategory.EMAIL)
            
            if extracted.get("phone"):
                user_profile.phone = extracted["phone"]
                user_profile.answered_categories.add(QuestionCategory.PHONE)
            
            if extracted.get("hometown"):
                user_profile.hometown = extracted["hometown"]
                user_profile.answered_categories.add(QuestionCategory.HOMETOWN)
            
            if extracted.get("profession"):
                user_profile.profession = extracted["profession"]
                user_profile.answered_categories.add(QuestionCategory.PROFESSION)
            
            if extracted.get("marital_status"):
                user_profile.marital_status = extracted["marital_status"]
                user_profile.answered_categories.add(QuestionCategory.MARITAL_STATUS)
            
            if extracted.get("has_children") is not None:
                user_profile.has_children = extracted["has_children"]
                user_profile.answered_categories.add(QuestionCategory.CHILDREN)
            
            if extracted.get("budget"):
                from domain.value_objects import Budget
                try:
                    budget_value = int(str(extracted["budget"]).replace("k", "000").replace("K", "000"))
                    user_profile.update_budget(Budget(min_amount=budget_value, max_amount=budget_value))
                except:
                    self.logger.warning(f"Could not parse budget: {extracted['budget']}")
            
            if extracted.get("location"):
                from domain.value_objects import Location
                user_profile.update_location(Location(city=extracted["location"]))
            
            if extracted.get("property_type"):
                from domain.value_objects import PropertyPreferences
                from domain.enums import PropertyType
                try:
                    prop_type = PropertyType(extracted["property_type"])
                    user_profile.update_property_preferences(PropertyPreferences(property_type=prop_type))
                except:
                    self.logger.warning(f"Could not parse property_type: {extracted['property_type']}")
            
            if extracted.get("rooms"):
                # Just store room count, don't try to create PropertyPreferences
                try:
                    room_count = int(extracted["rooms"])
                    user_profile.answered_categories.add(QuestionCategory.ROOMS)
                    self.logger.info(f"Extracted rooms: {room_count}")
                    # Store in property preferences if it exists, otherwise just mark as answered
                    if user_profile.property_preferences:
                        user_profile.property_preferences.min_rooms = room_count
                        user_profile.property_preferences.max_rooms = room_count
                except Exception as e:
                    self.logger.warning(f"Could not parse rooms: {extracted.get('rooms')}, error: {e}")
            
            # Store additional insights
            if extracted.get("hobbies"):
                user_profile.hobbies = extracted["hobbies"]
                user_profile.answered_categories.add(QuestionCategory.HOBBIES)
                self.logger.info(f"Extracted hobbies: {extracted['hobbies']}")
            
            if extracted.get("salary"):
                user_profile.estimated_salary = str(extracted["salary"])
                user_profile.answered_categories.add(QuestionCategory.SALARY)
                self.logger.info(f"Extracted salary: {extracted['salary']}")
            
            if extracted.get("estimated_salary_range"):
                user_profile.estimated_salary = extracted["estimated_salary_range"]
            
            if extracted.get("lifestyle_notes"):
                user_profile.lifestyle_notes = extracted["lifestyle_notes"]
            
            if extracted.get("pets"):
                # Store pets info in lifestyle notes for now
                pets_info = extracted["pets"]
                user_profile.answered_categories.add(QuestionCategory.PETS)
                if user_profile.lifestyle_notes:
                    user_profile.lifestyle_notes += f" | Pets: {pets_info}"
                else:
                    user_profile.lifestyle_notes = f"Pets: {pets_info}"
                self.logger.info(f"Extracted pets: {pets_info}")
            
            self.logger.info(f"Updated profile from message. Answered categories: {[cat.value for cat in user_profile.answered_categories]}")
            
        except Exception as e:
            self.logger.error(f"Error updating profile from message: {str(e)}", exc_info=True)
            # Don't raise - continue even if extraction fails
    
    def _format_analysis_response(self, analysis: dict) -> str:
        """Format analysis results into user-friendly message."""
        parts = []
        
        if analysis.get("summary"):
            parts.append(f"📊 **Analiz Özeti**\n{analysis['summary']}\n")
        
        if analysis.get("recommendations"):
            parts.append("🏠 **Öneriler:**")
            for i, rec in enumerate(analysis["recommendations"], 1):
                parts.append(f"{i}. {rec}")
            parts.append("")
        
        if analysis.get("key_considerations"):
            parts.append("⚠️ **Dikkat Edilmesi Gerekenler:**")
            for consideration in analysis["key_considerations"]:
                parts.append(f"• {consideration}")
            parts.append("")
        
        if analysis.get("budget_analysis"):
            parts.append(f"💰 **Bütçe Analizi:**\n{analysis['budget_analysis']}\n")
        
        if analysis.get("location_insights"):
            parts.append(f"📍 **Konum İçgörüleri:**\n{analysis['location_insights']}")
        
        return "\n".join(parts)
