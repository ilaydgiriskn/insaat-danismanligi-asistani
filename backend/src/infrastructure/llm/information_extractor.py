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
1. Kullanıcının verdiği net bilgileri çıkar.
2. **Soyisim (surname)**: Kullanıcı "Ali Yılmaz" dediyse Yılmaz'ı soyisim olarak al. Hiç verilmediyse `null` bırak. ASLA email adresinden isim veya soyisim çıkarma.
3. **Medeni Durum (marital_status)**: "evleneceğim", "nişanlıyım" gibi ifadeleri "evli/nişanlı" kategorisine yönlendir. 
4. **Maaş ve Bütçe AYRIMI**: 
   - `monthly_income`: Kullanıcının AYLIK geliri. Rakam olarak al. (Örn: "80k" -> 80000). ASLA "yüksek", "iyi" gibi yorum yapma.
   - `purchase_budget`: Ev almak için ayırdığı toplam bütçe. SADECE kullanıcı "ev için bütçem X" derse doldur. Maaştan türetme.
5. **Lokasyon Ayrımı**: 
   - `current_city`: Şu an yaşadığı şehir/ilçe. Şehir açıkça belirtilmediyse konuşma geçmişinden bul. (Örn: "Ordu" dedi, sonra "Şahinbey" dedi -> Şahinbey Ordu'da değilse bile kullanıcının beyanını esas al ya da bağlamı kontrol et).
   - `location`: Ev almak istediği yer.
6. 'answered_categories' listesine, mesajda cevabı bulunan kategorileri ekle.

Cevap formatı kesinlikle JSON olmalıdır.
"""

        try:
            response = await self.llm_service.generate_structured_response(
                prompt=prompt,
                system_message="Sen bilgi çıkarma uzmanısın. Kullanıcı mesajlarından yapılandırılmış bilgi çıkarırsın.",
                response_format={
                    "name": "string or null",
                    "surname": "string or null",
                    "email": "string or null",
                    "phone": "string or null",
                    "hometown": "string or null",
                    "current_city": "string or null", # NEW: Where they live now
                    "profession": "string or null",
                    "marital_status": "string or null",
                    "has_children": "boolean or null",
                    "purchase_budget": "number or null",
                    "monthly_income": "number or null",
                    "location": "string or null", # Preferred location
                    "property_type": "string or null",
                    "rooms": "number or null",
                    "hobbies": "array or null",
                    "lifestyle_notes": "string or null",
                    "answered_categories": "array of category names"
                }
            )
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error extracting information: {str(e)}")
            return {}
