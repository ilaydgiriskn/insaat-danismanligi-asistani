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
   - ÖNEMLİ: "Bilmiyorum", "Bilmem", "Hatırlamıyorum", "Öğretmen", "Doktor" gibi kelimeleri ASLA isim olarak alma. Sadece gerçek özel isimleri (Ali, Ayşe vb.) al.
3. **Medeni Durum (marital_status)**: "evleneceğim", "nişanlıyım" gibi ifadeleri "evli/nişanlı" kategorisine yönlendir. 
4. **Maaş ve Bütçe AYRIMI**: 
   - `monthly_income`: Kullanıcının AYLIK geliri. Rakam olarak al. (Örn: "80k" -> 80000). ASLA "yüksek", "iyi" gibi yorum yapma.
   - `purchase_budget`: Ev almak için ayırdığı toplam bütçe. SADECE kullanıcı "ev için bütçem X" derse doldur. Maaştan türetme.
5. **Lokasyon Ayrımı**: 
   - `location`: Ev almak istediği yer.
6. **Sosyal Alanlar (social_amenities)**: Spor salonu, havuz, yürüyüş parkuru gibi talepler.
   - Eğer kullanıcı "yok", "farketmez", "önemli değil" derse BOŞ LİSTE `[]` döndür. 
   - Konu hiç geçmediyse `null` döndür (Veriyi ezmemek için).
7. **Oda Sayısı (rooms)**: 
   - "3 artı 1", "üç artı bir", "3 oda" -> 3 olarak al.
   - "5 oda istiyorum", "5 odalı" -> 5 olarak al.
   - "çalışma odası", "misafir odası" gibi detaylar varsa bile, kullanıcının ANA beyanını (Örn: "5 oda") esas al.
   - Sadece rakam (number) olarak dön. Bulunamazsa `null` dön.
8. **Memleket (hometown)**:
   - "Bursalıyım" -> Bursa, "Antepliyim" -> Gaziantep (Antep değil).
   - "Köklerim X şehrinde" -> X.
9. **Satın Alma Amacı (purchase_purpose)**: 
   - "Yatırım" olarak işaretle: "Kiraya vereceğim", "Değerlensin", "Yatırımlık", "Yatırım amacım var".
   - "Oturum" olarak işaretle: "Ailemle yaşayacağım", "Kendim oturacağım", "Oturcam", "Kendim kalcam", "Taşınmak istiyorum", "Oturmak için".
   - "Hem yatırım hem oturum": İkisi de belirtilirse.
10. 'answered_categories' listesine, mesajda cevabı bulunan kategorileri MUTLAKA ekle. Örneğin 'purchase_purpose' dolduysa listeye 'PURCHASE_PURPOSE' ekle.

49. **Telefon Numarası Kontrolü**:
   - Eğer kullanıcı bir numara yazdıysa (532...) ama 10 haneden kısaysa (örn: "532 123", "0543", "505 123 45"), 'phone' alanını NULL bırak.
   - Ve 'validation_warnings' listesine 'phone_invalid' ekle.
   - Sadece geçerli (10-11 haneli) numaraları 'phone' alanına al.

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
                    "social_amenities": "array of strings",
                    "purchase_purpose": "string or null",
                    "location": "string or null", # Preferred location
                    "property_type": "string or null",
                    "rooms": "number or string or null", # Changed to allow string parsing fallback
                    "hobbies": "array or null",
                    "lifestyle_notes": "string or null",
                    "answered_categories": "array of category names",
                    "validation_warnings": "array of strings" # New field for validation errors
                }
            )
            
            return response
            
        except Exception as e:
            self.logger.error(f"Error extracting information: {str(e)}")
            return {}
