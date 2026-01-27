"""Information extraction service using LLM."""

import json
from typing import Optional
from application.interfaces import ILLMService
from domain.enums import QuestionCategory
from infrastructure.config import get_logger


class InformationExtractor:
    """Extract structured information from user messages using LLM."""
    
    def __init__(self, llm_service: ILLMService):
        self.llm_service = llm_service
        self.logger = get_logger(self.__class__.__name__)
    
    async def extract_profile_info(
        self,
        message: str,
        conversation_history: str = ""
    ) -> dict:
        """Extract profile information from user message."""
        
        prompt = f"""Kullanıcının son mesajından profil bilgilerini çıkar. Eğer mesaj kısa veya bağlamsal ise (örneğin "evet", "hayır", "farketmez"), MUTLAKA konuşma geçmişindeki son soruya bakarak neye cevap verildiğini anla.

Son Mesaj: "{message}"

Konuşma Geçmişi (Sondan başa doğru):
{conversation_history}

GÖREV:
1. Kullanıcının verdiği net bilgileri (isim, email, meslek, medeni durum vb.) çıkar.
2. Bağlamsal Cevaplar: Eğer son soru "Çocuğunuz var mı?" ise ve mesaj "Evet" ise, `has_children` değerini `true` yap. Bu mantığı tüm sorular için uygula.
3. 'answered_categories' listesine, mesajda cevabı bulunan kategorileri (name, budget, family vb.) ekle.
4. Çıkarımlar: `estimated_salary_range` (meslekten) ve `lifestyle_notes` (hobilerden) alanlarını doldur.

Cevap formatı kesinlikle JSON olmalıdır."""

        try:
            response = await self.llm_service.generate_structured_response(
                prompt=prompt,
                system_message="Sen bilgi çıkarma uzmanısın. Kullanıcı mesajlarından yapılandırılmış bilgi çıkarırsın.",
                response_format={
                    "name": "string or null",
                    "email": "string or null",
                    "phone": "string or null",
                    "hometown": "string or null",
                    "profession": "string or null",
                    "marital_status": "string or null",
                    "has_children": "boolean or null",
                    "budget": "number or null",
                    "location": "string or null",
                    "property_type": "string or null",
                    "rooms": "number or null",
                    "hobbies": "array or null",
                    "estimated_salary_range": "string or null",
                    "lifestyle_notes": "string or null",
                    "family_structure": "string or null",
                    "answered_categories": "array of category names"
                }
            )
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error extracting information: {str(e)}")
            return {}
