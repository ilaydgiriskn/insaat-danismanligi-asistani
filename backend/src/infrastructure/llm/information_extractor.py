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
        
        prompt = f"""Kullanıcının mesajından ve konuşma geçmişinden profil bilgilerini çıkar.

Kullanıcı Mesajı: "{message}"

Konuşma Geçmişi:
{conversation_history}

GÖREV:
1. Kullanıcının verdiği bilgileri (isim, email, meslek, medeni durum vb.) çıkar.
2. Sadece kesin bilgileri al. Tahmin yapma.
3. 'answered_categories' listesine, mesajda cevabı bulunan kategorileri ekle.

Kategoriler:
- name, email, phone, hometown, profession, marital_status, has_children, budget, location, property_type, rooms, salary, hobbies, pets

AYRICA ŞU ÇIKARIMLARI YAP (Bunlar kategorilere eklenmez):
- estimated_salary_range: Meslekten tahmini maaş aralığı
- lifestyle_notes: Hobilerden yaşam tarzı notları

Cevap formatı JSON olmalı."""

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
