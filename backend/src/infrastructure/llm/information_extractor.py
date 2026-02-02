"""Information extraction service using LLM."""

import json
import asyncio
from typing import Optional
from application.interfaces import ILLMService
from domain.enums import QuestionCategory
from infrastructure.config import get_logger


class InformationExtractor:
    """Extract structured information from user messages using LLM."""
    
    def __init__(self, llm_service: ILLMService):
        self.llm_service = llm_service
        self.logger = get_logger(self.__class__.__name__)
        self.max_retries = 2
        self.timeout_seconds = 10  # Optimized for deepseek-chat
    
    async def extract_profile_info(
        self,
        message: str,
        conversation_history: str = ""
    ) -> dict:
        """Extract profile information from user message with timeout and retry."""
        
        prompt = f"""Kullanıcının son mesajından profil bilgilerini çıkar. Eğer mesaj kısa veya bağlamsal ise (örneğin "evet", "hayır", "farketmez"), MUTLAKA konuşma geçmişindeki son soruya bakarak neye cevap verildiğini anla.

Son Mesaj: "{message}"

Konuşma Geçmişi (Sondan başa doğru):
{conversation_history}

GÖREV:
1. Kullanıcının verdiği net bilgileri çıkar.
2. **İsim ve Soyisim Extraction (ÇOK ÖNEMLİ!)**:
   - Kullanıcı "ilayda girişken", "ahmet yılmaz", "ali veli" gibi İKİ KELİME yazdıysa:
     * İLK kelime → name (isim)
     * İKİNCİ kelime → surname (soyisim)
   - Örnek: "ilayda girişken" → name: "İlayda", surname: "Girişken"
   - Örnek: "ahmet ali" → name: "Ahmet", surname: "Ali"
   
   - **CLARIFICATION Mesajları (Kullanıcı açıklama yapıyorsa):**
     * "girişken dedim ya", "yılmaz dedim işte", "soyismim bu" → Konuşma geçmişine bak!
     * Kullanıcı önceki mesajında verdiği bilgiyi tekrar belirtiyor
     * conversation_history'deki son user mesajına bak, orada ne varsa al
     * Örnek: Geçmiş "ilayda girişken", Şimdi "girişken dedim ya" → surname: "Girişken"
   
   - "Bilmiyorum", "Bilmem", "Öğretmen", "Doktor" → ASLA isim olarak alma
   - E-mail adresinden isim çıkarma!

3. **Medeni Durum (marital_status)**: "evleneceğim", "nişanlıyım" gibi ifadeleri "evli/nişanlı" kategorisine yönlendir. 
4. **Maaş ve Bütçe AYRIMI**: 
   - `monthly_income`: Kullanıcının AYLIK geliri. Rakam olarak al. (Örn: "80k" -> 80000). ASLA "yüksek", "iyi" gibi yorum yapma.
   - `purchase_budget`: Ev almak için ayırdığı toplam bütçe. SADECE kullanıcı "ev için bütçem X" derse doldur. Maaştan türetme.
5. **Lokasyon Ayrımı - 3 FARKLI KAVRAM**:
   - **`current_city`** (ŞU AN NEREDE YAŞIYOR?): "Ankara'da yaşıyorum", "Kızılay'da oturuyorum", "İzmir'deyim" -> ŞU ANKİ ikamet yeri
   - **`location`** (EV ALMAK İSTEDİĞİ YER): "Çankaya'da ev arıyorum", "Kadıköy'de ev almak istiyorum" -> Hedef bölge
     * Eğer kullanıcı "aynı yerde", "burada" derse, current_city'yi location'a da kopyala
   - **`hometown`** (MEMLEKET): "Bursalıyım", "Antepliyim" -> Nereli olduğu (Sadece "-liyim/-lıyım" ifadelerinde doldur)
   - ⚠️ Bu 3 kavramı ASLA karıştırma! Her biri ayrı field.
6. **Sosyal Alanlar (social_amenities)**: Spor salonu, havuz, yürüyüş parkuru gibi talepler.
   - "Havuz istiyorum", "Spor salonu olsun", "Yürüyüş parkuru" -> ["Havuz", "Spor Salonu", "Yürüyüş Parkuru"]
   - "Park olsun", "Yeşil alan", "Fitness" -> ["Park", "Yeşil Alan", "Fitness"]
   - "Basketbol sahası", "Tenis kortu", "Kapalı otopark" -> ["Basketbol Sahası", "Tenis Kortu", "Kapalı Otopark"]
   - ⚠️ "havuz da keyif yapmak", "spor yapmak icin" gibi ifadelerde de ÇIKAR: ["Havuz", "Spor Salonu"]
   - "cocuklarla havuz", "esimle spor" -> ["Havuz", "Spor Salonu"]
   - Kullanıcı "HAVUZ" veya "SPOR" kelimesini kullandıysa MUTLAKA listeye ekle!
   - Eğer kullanıcı "yok", "farketmez", "önemli değil" derse BOŞ LİSTE `[]` döndür. 
   - Konu hiç geçmediyse `null` döndür (Veriyi ezmemek için).
7. **Oda Sayısı (rooms)**: 
   - "3 artı 1", "üç artı bir", "3 oda" -> 3 olarak al.
   - "5 oda istiyorum", "5 odalı" -> 5 olarak al.
   - "çalışma odası", "misafir odası" gibi detaylar varsa bile, kullanıcının ANA beyanını (Örn: "5 oda") esas al.
   - Sadece rakam (number) olarak dön. Bulunamazsa `null` dön.
8. **Memleket (hometown)**:
   - "Bursalıyım" -> Bursa, "Antepliyim" -> Gaziantep (Antep değil).
   - ⚠️ DİKKAT: "Gaziantep'te yaşıyorum" demek MEMLEKETİ Gaziantep DEMEK DEĞİLDİR. Sadece "Nerelisin?" cevabı ise doldur.
   - İkametgah (current_city) ile Memleket'i (hometown) KARIŞTIRMA! Emin değilsen null bırak.
9. **Satın Alma Amacı (purchase_purpose)**: 
   - "Yatırım" olarak işaretle: "Kiraya vereceğim", "Değerlensin", "Yatırımlık", "Yatırım amacım var".
   - "Oturum" olarak işaretle: "Ailemle yaşayacağım", "Kendim oturacağım", "Oturcam", "Kendim kalcam", "Taşınmak istiyorum", "Oturmak için".
   - "Hem yatırım hem oturum": İkisi de belirtilirse.
9. **Birikim Durumu (savings_info)**:
   - "Evet biriktirdim", "20 bin TL param var", "100k birikimim var" -> Miktarı yaz veya "Var" yaz.
   - "Yok", "Hiç yok", "Biriktiremedim" -> "Yok" yaz.
   - Konu geçmediyse null döndür. Eğer kullanıcı "bilmiyorum", "söylemek istemiyorum" derse 'answered_categories'e 'SAVINGS' ekle ama null bırak.
10. **Kredi Kullanımı (credit_usage)**:
   - "Evet kredi çekeceğim", "Bankadan kredi alacağım", "Konut kredisi" -> "Evet" veya detaylı cevabı yaz.
   - "Hayır", "Kredi kullanmayacağım", "Peşin alacağım" -> "Hayır" yaz.
   - Konu geçmediyse null döndür. Kullanıcı cevap vermek istemezse 'answered_categories'e 'CREDIT_USAGE' ekle, null bırak.
11. **Takas Tercihi (exchange_preference)**:
   - "Arabamı takas edeceğim", "Eski evimi vereceğim", "Takas düşünüyorum" -> "Evet" veya detayı yaz (araba/ev).
   - "Hayır", "Takas yapmayacağım", "Yok" -> "Hayır" yaz.
   - Konu geçmediyse null döndür. Kullanıcı cevap vermek istemezse 'answered_categories'e 'EXCHANGE' ekle, null bırak.
12. **Sosyal Alanlar (social_amenities)** - ÇOK ÖNEMLİ!:
   - Liste olarak döndür: ["havuz", "spor salonu", "basketbol sahası", "çocuk parkı", "yürüyüş yolu"]
   - "Basketbol sahası istiyorum" -> social_amenities: ["basketbol sahası"], answered_categories: ['SOCIAL_AMENITIES']
   - "Havuz ve spor salonu" -> social_amenities: ["havuz", "spor salonu"]
   - "İstemiyorum"/"Yok" -> social_amenities: [], answered_categories: ['SOCIAL_AMENITIES']
   - Konu geçmediyse null döndür
   - ⚠️ DİKKAT: Kullanıcı "basketbol sahası" gibi TEK bir şey söylese bile answered_categories'e 'SOCIAL_AMENITIES' EKLE!
13. **answered_categories Kuralı**:
   - Kullanıcı bir soruya cevap verdiyse (null olsa bile), o kategoriyi answered_categories'e EKLE
   - Örnek: "İletişim paylaşmak istemiyorum" -> email: null, phone: null, ama answered_categories: ['EMAIL', 'PHONE_NUMBER']
   - Örnek: "Basketbol sahası olsun" -> social_amenities: ["basketbol sahası"], answered_categories: ['SOCIAL_AMENITIES']


49. **Telefon Numarası Kontrolü**:
   - Eğer kullanıcı TELEFON VERMEK İSTEMİYORSA ("vermek istemiyorum", "paylaşmak istemiyorum", "telefonu vermeyeceğim", "numara yok" gibi), 'answered_categories' listesine 'PHONE_NUMBER' ekle ve 'phone' null bırak. Bu durumda 'phone_invalid' EKLEME.
   - Eğer kullanıcı bir numara YAZDIYSA (532...) ama 10 haneden kısaysa (örn: "532 123", "0543", "505 123 45"), 'phone' alanını NULL bırak VE 'validation_warnings' listesine 'phone_invalid' ekle.
   - Sadece geçerli (10-11 haneli) numaraları 'phone' alanına al.

Cevap formatı kesinlikle JSON olmalıdır.
"""

        for attempt in range(self.max_retries + 1):
            try:
                self.logger.info(f"Information extraction attempt {attempt + 1}/{self.max_retries + 1}")
                
                # Add timeout to LLM call
                response = await asyncio.wait_for(
                    self.llm_service.generate_structured_response(
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
                            "savings_info": "string or null",
                            "credit_usage": "string or null", 
                            "exchange_preference": "string or null",
                            "location": "string or null", # Preferred location
                            "property_type": "string or null",
                            "rooms": "number or string or null", # Changed to allow string parsing fallback
                            "hobbies": "array or null",
                            "lifestyle_notes": "string or null",
                            "answered_categories": "array of category names",
                            "validation_warnings": "array of strings" # New field for validation errors
                        }
                    ),
                    timeout=self.timeout_seconds
                )
                
                self.logger.info(f"✅ Information extraction successful on attempt {attempt + 1}")
                return response
                
            except asyncio.TimeoutError:
                self.logger.warning(f"⏱️ Information extraction timeout (attempt {attempt + 1}/{self.max_retries + 1})")
                if attempt < self.max_retries:
                    await asyncio.sleep(1)  # Wait 1 second before retry
                    continue
                else:
                    self.logger.error(f"❌ Information extraction failed after {self.max_retries + 1} attempts (timeout)")
                    return {}
                    
            except json.JSONDecodeError as e:
                self.logger.error(f"❌ JSON parsing error in information extraction: {str(e)}")
                if attempt < self.max_retries:
                    await asyncio.sleep(1)
                    continue
                else:
                    return {}
                    
            except Exception as e:
                self.logger.error(f"❌ Error extracting information (attempt {attempt + 1}): {str(e)}", exc_info=True)
                if attempt < self.max_retries:
                    await asyncio.sleep(1)
                    continue
                else:
                    # Return empty dict as safe fallback
                    self.logger.error(f"❌ Information extraction completely failed after {self.max_retries + 1} attempts")
                    return {}

