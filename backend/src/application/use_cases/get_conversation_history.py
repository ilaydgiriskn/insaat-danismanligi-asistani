"""Use Case for retrieving conversation history and state."""

from uuid import UUID
from typing import Dict, Any, List
from datetime import datetime

from domain.repositories import IUserRepository, IConversationRepository
from infrastructure.config import get_logger

class GetConversationHistoryUseCase:
    """Retrieve full conversation history and state for restoration."""
    
    def __init__(
        self,
        user_repository: IUserRepository,
        conversation_repository: IConversationRepository,
    ):
        self.user_repo = user_repository
        self.conversation_repo = conversation_repository
        self.logger = get_logger(self.__class__.__name__)
        
    async def execute(self, session_id: str) -> Dict[str, Any]:
        """
        Get history for a session.
        Returns:
            {
                "session_id": str,
                "messages": List[dict],
                "state": {
                    "is_complete": bool,
                    "has_analysis": bool,
                    "analysis_content": str | None,
                    "user_name": str | None
                }
            }
        """
        try:
            self.logger.info(f"🔄 Fetching history for session: {session_id}")
            
            # 1. Get User Profile first (since session_id is linked to profile)
            profile = await self.user_repo.get_by_session_id(session_id)
            if not profile:
                self.logger.warning(f"⚠️ Profile not found for session: {session_id}")
                return None

            # 2. Get Conversation linked to this profile
            conversation = await self.conversation_repo.get_by_user_profile_id(profile.id)
            if not conversation:
                self.logger.warning(f"⚠️ Conversation not found for profile: {profile.id}")
                return None
                
            
            # 3. Format Messages
            formatted_messages = []
            for msg in conversation.messages:
                formatted_messages.append({
                    "role": msg.role.value,
                    "content": msg.content,
                    "timestamp": msg.timestamp,
                    # type/category fields might be stored in future metadata
                })
                
            # 4. Determine State
            # Check for analysis content in recent assistant messages or profile logic
            analysis_content = None
            is_complete = False
            
            # Simple heuristic: If we have an analysis response in history
            # Ideally store this in a dedicated field, but for now we scan
            # Or leverage existing logic where 'analysis' is returned in process_user_message
            
            # Check if profile is mature
            answered_count = len(profile.answered_categories) if profile and profile.answered_categories else 0
            profile_completion = answered_count / 14.0
            
            # Check if "closing" message exists
            last_msg = conversation.get_last_assistant_message()
            if last_msg and ("iletişime geçecektir" in last_msg.content or "Teşekkürler" in last_msg.content):
                is_complete = True
            
            # Note: The actual analysis text (detailed) isn't persisted directly in a simple field yet
            # It's generated on the fly or embedded in PDF. 
            # Ideally frontend should cache it, but backend can try to reconstruct or 
            # just indicate it's done. 
            # For now, we return 'is_complete' so frontend knows to show states.
            
            return {
                "session_id": session_id,
                "messages": formatted_messages,
                "state": {
                    "is_complete": is_complete,
                    "user_name": f"{profile.name} {profile.surname}" if profile else None,
                    "profile_completion": profile_completion
                }
            }
            
        except Exception as e:
            self.logger.error(f"❌ Error fetching history: {str(e)}", exc_info=True)
            raise e
