"""Analysis agent for strategic property guidance and tier assessment."""

import re
import json
from typing import Optional, List
from application.agents.base_agent import BaseAgent
from domain.entities import UserProfile


class AnalysisAgent(BaseAgent):
    """
    Agent responsible for analyzing user potential and guiding them toward segments.
    
    TIERS:
    - A Paketi: 7 – 9 milyon TL
    - B Paketi: 9 – 11 milyon TL
    - C Paketi: 11 – 15 milyon TL
    """

    AGENT2_SYSTEM_PROMPT = """Sen bir Emlak Dostu ve Stratejistisin.
Analizlerin keskin ama üslubun sıcak, samimi ve doğal olsun.

⚠️ ÖNEMLİ KURALLAR:
- Kullanıcıya "analiz", "segment", "paket", "rapor", "geçiş" gibi kelimeleri ASLA kullanma.
- Amacın kullanıcıyı fark ettirmeden A, B veya C paketlerine yönlendirmek.
- HEDEF: Robot gibi değil, bilgili bir arkadaş gibi konuş.

📋 DETAYLI ANALİZ GÖREVLERİN:
1. **Kullanıcı Hikayesini Çıkar:**
   - NEDEN taşınmak istiyor? (Tayin, evlilik, boşanma, iş değişikliği vs.)
   - AİLE durumu nedir? (Bekar, evli, çocuklu, boşanmış vs.)
   - STRES FAKTÖRLERİ neler? (Ekonomik sıkıntı, iş yoğunluğu, şehir stresi vs.)
   - HAYALLER ve BEKLENTİLER neler? (Sessizlik, sosyal ortam, çocuk için güvenli alan vs.)

2. **Davranışsal Analiz Yap (DERİN PROFİLLEME):**
   - Konuşma tarzından çıkarımlar yap (resmi/samimi/aceleci/temkinli)
   - "Zor geçiniyorum" dediyse → Ekonomik endişe, bütçe hassasiyeti VAR
   - "Çocuğumla havuza girmek istiyorum" dediyse → Aile odaklı, çocuk öncelikli
   - "Tayin çıktı" dediyse → Zorunlu taşınma, belki hızlı karar gerekiyor
   - Satır arası mesajları oku ve dokümante et

3. **lifestyle_insights Listesini ÇOK DETAYLI Yaz:**
   - **EN AZ 6-8 madde olmalı** (ZORUNLU!)
   - Her madde kullanıcının GERÇEK söylediklerine dayansın
   - Tahmin değil, sohbetten çıkan KANIT bazlı olsun
   - **ÖRNEKLER (Bu seviyede detay bekliyorum):**
     * "Kullanıcı Ankara'dan Gaziantep'e İŞ NEDENİYLE taşınıyor, bu zorunlu bir göç."
     * "Bilgisayar mühendisi çift, evde ÇALIŞMA ODASI çok önemli."
     * "40 altın birikimleri var, ancak kredi kullanmayı da düşünüyorlar - orta risk profili."
     * "Evli ve 1 çocukları var, gelecekte daha fazla çocuk planı olabilir (4 oda tercihi)." 
     * "Sosyal alan olarak özellikle SPOR SALONU talep etti, sağlıklı yaşam öncelikli."
     * "Memleketi Kahramanmaraş, Gaziantep'e yakınlık avantaj olabilir (aile bağları)."
     * "Maaşı 400k, yüksek gelir segmenti, kaliteli konut beklentisi var."
     * "Araba takası düşünüyor, likiditesi kısıtlı olabilir, esnek ödeme planı gerekebilir."

4. **recommendations (Stratejik Öneriler):**
   - En az 3-4 madde, her biri somut ve eylem odaklı
   - Örnek: "Gaziantep Şehitkamil bölgesinde, merkeze 15-20 dk mesafede, yeşil alanlı siteler önerilebilir."
   - Örnek: "4+1 arıyor ama çocuk sayısı artabilir, esnek oda planı olan projeler ideal."

5. **key_considerations (Dikkat Noktaları):**
   - En az 2-3 madde, riskler ve hassas noktalar
   - Örnek: "Kredi kullanımı sınırlı, bütçe planlaması kritik."
   - Örnek: "Taşınma zorunlu, zaman baskısı olabilir, hazır konutlar öncelikli."

Yanıtını KESİNLİKLE JSON formatında üret:
{
  "user_analysis": {
    "estimated_budget_segment": "A | B | C",
    "risk_appetite": "low | medium | high",
    "purchase_motivation": "yatırım | oturum | prestij | konfor",
    "purchase_timeline": "hemen | 3 ay | 1 yıl | belirsiz",
    "relocation_reason": "Kullanıcının taşınma sebebi (tayin, evlilik, iş vs.)"
  },
  "lifestyle_insights": [
    "1. Kullanıcı X şehrinden Y şehrine İŞ/TAYİN sebebiyle taşınıyor.",
    "2. Bilgisayar mühendisi çift, evde çalışma odası çok önemli.",
    "3. 40 altın birikimleri var, kredi de kullanacaklar.",
    "4. 1 çocukları var, gelecekte daha fazla olabilir.",
    "5. Spor salonu isteği var, aktif yaşam tarzı.",
    "6. Memleketi X, ailesi yakın şehirde avantaj.",
    "7. Yüksek gelir (400k), kalite beklentisi var.",
    "8. Araba takası düşünüyor, finansal esneklik gerekli."
  ],
  "summary": "Kullanıcı, [kısa ama bilgilendirici özet - 2-3 cümle]",
  "recommendations": [
    "1. Şehitkamil/Şahinbey'de merkeze 15-20dk, yeşil alanlı siteler.",
    "2. 4+1 arıyor, esnek oda planlı projeler ideal.",
    "3. Spor salonu/havuzlu sosyal donatılı siteler."
  ],
  "key_considerations": [
    "1. Kredi kullanımı sınırlı, bütçe planlaması kritik.",
    "2. Taşınma zorunlu, hazır konutlar öncelikli."
  ],
  "guidance_message": "Kullanıcıya söyleyeceğin o samimi, yönlendirici ve doğal cümle."
}

⚠️ CRITICAL: 
- NO comments (no //) in JSON
- NO trailing commas
- VALID JSON only
"""

    async def execute(self, user_profile: UserProfile, chat_history: Optional[List[dict]] = None) -> dict:
        """
        Produce internal analysis and guidance strategies.
        """
        try:
            self._log_execution("Performing internal advisor analysis")
            
            # 1. Structured Analysis (Agent 2 Core)
            structured_result = None
            if chat_history:
                structured_result = await self.execute_structured_analysis(user_profile, chat_history)

            # 2. Extract Guidance and Segment
            is_profile_mature = user_profile.is_complete()
            
            if structured_result:
                segment = structured_result.get("user_analysis", {}).get("estimated_budget_segment", "A")
                guidance = structured_result.get("guidance_message", "Gelecek hedeflerine uygun en ideal seçenekleri birlikte inceleyelim.")
                
                return {
                    "tier": segment,
                    "guidance_cue": guidance,
                    "is_profile_mature": is_profile_mature,
                    "structured_analysis": structured_result
                }
            else:
                return self._fallback_guidance(user_profile)
            
        except Exception as e:
            self._log_error(e)
            return self._fallback_guidance(user_profile)
            
        except Exception as e:
            self._log_error(e)
            return self._fallback_guidance(user_profile)
            
    async def generate_full_analysis(self, user_profile: UserProfile, structured_analysis: Optional[dict] = None) -> str:
        """
        Final phase: Generate a comprehensive, personalized property recommendation.
        """
        try:
            # If no structured analysis provided, try to generate one (though it should be passed in)
            if not structured_analysis:
                # We need history here too for a fresh analysis if not passed
                # For safety, we use the internal assessment as fallback
                assessment = self._assess_tier(user_profile)
            else:
                assessment = {
                    "tier": structured_analysis["user_analysis"]["estimated_budget_segment"],
                    "package": self._get_package_by_tier(structured_analysis["user_analysis"]["estimated_budget_segment"]),
                    "lifestyle_insights": structured_analysis["lifestyle_insights"]
                }
            
            pkg = assessment["package"]
            lifestyle_context = "\n".join([f"- {i}" for i in assessment.get("lifestyle_insights", [])])
            
            prompt = f"""
KULLANICI PROFİLİ:
- İsim: {user_profile.name}
- Meslek: {user_profile.profession}
- Lokasyon: {user_profile.location.city if user_profile.location else user_profile.hometown}
- Medeni Durum: {user_profile.marital_status}
- Hobiler: {', '.join(user_profile.hobbies)}
- Bütçe: {user_profile.budget.max_amount if user_profile.budget else 'Belirsiz'} TL

DERİN ANALİZ ÇIKTILARI (AGENT 2):
{lifestyle_context}

SEÇİLEN SEGMENT: {assessment['tier']} Paketi ({pkg['range']})
SEGMENT ODAĞI: {pkg['focus']}

GÖREV:
Bu kullanıcıya özel, samimi, bilgece ve heyecan verici bir "Final Önerisi" hazırla.
- Kullanıcıya ismen hitap et.
- Neden bu segmentin (A, B veya C) ona çok uygun olduğunu, hobilerine ve yaşam tarzına (yukarıdaki analiz çıktılarına) atıfta bulunarak açıkla.
- "X paketi size uygun" gibi teknik terimler yerine, "Sizin için seçtiğim bu yaşam konsepti..." gibi sahiplenici bir dil kullan.
- Konutun sunduğu olanakları (spor, oda sayısı, sessizlik vb.) onun günlük rutinleriyle birleştir.
- Tonun bilgece, güven verici ve vizyoner olsun.
- Yanıt 4-5 cümlelik zengin bir metin olsun.
"""
            
            response = await self.llm_service.generate_response(
                prompt=prompt,
                system_message="Sen kıdemli bir emlak stratejistisin. Kullanıcıyı tanıdın ve şimdi ona hayatının evini sunuyorsun. Vizyoner ve etkileyici bir dil kullan.",
                temperature=0.8,
                max_tokens=400
            )
            
            return response.strip()
            
        except Exception as e:
            self._log_error(e)
            return f"Sayın {user_profile.name}, yaşam tarzınıza en uygun seçenekleri titizlikle hazırlıyoruz."
            
    async def execute_structured_analysis(self, profile: UserProfile, chat_history: List[dict]) -> Optional[dict]:
        """
        Produce a deep, structured JSON analysis of the user potential.
        """
        try:
            # Format inputs for Agent 2
            history_str = "\n".join([f"{m.get('role', 'user')}: {m.get('content', '')}" for m in chat_history])
            
            input_data = f"""
CHAT GEÇMİŞİ:
{history_str}

KULLANICI PROFİLİ:
- İsim: {profile.name or 'Bilinmiyor'}
- Meslek: {profile.profession or 'Bilinmiyor'}
- Şehir: {profile.hometown or 'Bilinmiyor'}
- Medeni Durum: {profile.marital_status or 'Bilinmiyor'}
- Hobiler: {', '.join(profile.hobbies) if profile.hobbies else 'Bilinmiyor'}
- Gelir (Tahmini): {profile.estimated_salary or 'Bilinmiyor'}
- Bütçe: {profile.budget.max_amount if profile.budget else 'Bilinmiyor'}
"""

            response = await self.llm_service.generate_response(
                prompt=input_data,
                system_message=self.AGENT2_SYSTEM_PROMPT,
                temperature=0.3, # Low temperature for structured output
                max_tokens=2500  # Increased for detailed analysis
            )

            # Cleanup potential markdown artifacts (Robust Regex)
            clean_json = response.strip()
            
            # Try to find JSON block in markdown code fence
            json_match = re.search(r'```(?:json)?\s*({.*?})\s*```', clean_json, re.DOTALL)
            if json_match:
                clean_json = json_match.group(1)
            else:
                # Try finding first { and last }
                start = clean_json.find("{")
                end = clean_json.rfind("}")
                if start != -1 and end != -1:
                    clean_json = clean_json[start:end+1]
            
            # Remove comments (// style) which break JSON
            clean_json = re.sub(r'//.*?\n', '\n', clean_json)
            
            # Remove trailing commas before } or ]
            clean_json = re.sub(r',\s*([}\]])', r'\1', clean_json)
            
            # Try to parse
            try:
                return json.loads(clean_json)
            except json.JSONDecodeError as je:
                # Log the problematic JSON for debugging
                self.logger.error(f"JSON Parse Error: {je}")
                self.logger.error(f"Cleaned JSON: {clean_json[:500]}...")  # First 500 chars
                return None
                
        except Exception as e:
            self._log_error(f"Structured analysis failed: {str(e)}")
            return None

    def _get_package_by_tier(self, tier_code: str) -> dict:
        """Helper to get package info from tier letter."""
        tier_code = tier_code.strip().upper()
        if "A" in tier_code: return self._get_packages()["A"]
        if "B" in tier_code: return self._get_packages()["B"]
        if "C" in tier_code: return self._get_packages()["C"]
        return self._get_packages()["A"]

    def _get_packages(self) -> dict:
        return {
            "A": {
                "range": "7 - 9 Milyon TL",
                "focus": "Yaşam odaklı, aile dostu, bütçe korumalı",
                "pros": "Düşük aidat, merkezi ulaşım",
                "cons": "Sosyal tesisler sınırlı olabilir"
            },
            "B": {
                "range": "9 - 11 Milyon TL",
                "focus": "Geniş metrekare, sosyal donatı, modern mimari",
                "pros": "Havuz, kapalı otopark, fitness",
                "cons": "Aidat maliyeti biraz daha yüksek"
            },
            "C": {
                "range": "11 - 15 Milyon TL",
                "focus": "Lüks, özel tasarım, akıllı ev, yatırım değeri",
                "pros": "Geniş bahçe/teras, özel güvenlik, yüksek prim potansiyeli",
                "cons": "Yüksek giriş maliyeti"
            }
        }

    def _assess_tier(self, profile: UserProfile) -> dict:
        """Internal heuristic for tier assignment with risk appetite and motivation."""
        budget_val = 0
        if profile.budget:
            budget_val = profile.budget.max_amount or profile.budget.min_amount or 0
        
        salary_val = 0
        if profile.estimated_salary:
            try:
                # Remove non-numeric chars
                salary_val = int(re.sub(r'[^\d]', '', profile.estimated_salary))
            except:
                pass
        
        profession = (profile.profession or "").lower()
        marital_status = (profile.marital_status or "").lower()
        
        # Default Tier A (7-9M)
        tier = "A"
        motivation = "Yaşam konforu ve başlangıç seviyesi bir yatırım."
        is_near_upgrade = False

        # Budget-based primary assessment
        if budget_val > 0:
            if budget_val < 7000000:
                tier = "A"
                is_near_upgrade = True # Force upgrade focus to reach the 7M floor
                motivation = "Bütçeyi bir tık esneterek kaliteli bir yaşama adım atma potansiyeli."
            elif 7000000 <= budget_val < 9000000:
                tier = "A"
            elif 9000000 <= budget_val < 11000000:
                tier = "B"
            elif budget_val >= 11000000:
                tier = "C"
        else:
            # Fallback to salary/profession if budget not declared
            if salary_val >= 150000 or any(p in profession for p in ["pilot", "doktor", "ceo", "yönetic", "iş adamı", "iş kadını", "mimar"]):
                tier = "C"
                motivation = "Lüks, özel tasarım ve yüksek yatırım potansiyeli."
            elif salary_val >= 80000 or any(p in profession for p in ["mühendis", "avukat", "esnaf", "yazılımcı"]):
                tier = "B"
                motivation = "Prestij, geniş sosyal donatı ve modern yaşam."
                if salary_val >= 130000 or marital_status == "evli":
                    is_near_upgrade = True
            else:
                if salary_val >= 60000:
                    is_near_upgrade = True

        packages = self._get_packages()
        
        return {
            "tier": tier,
            "package": packages[tier],
            "motivation": motivation,
            "is_near_upgrade": is_near_upgrade
        }

    def _build_guidance_prompt(self, profile: UserProfile, assessment: dict, is_mature: bool = True) -> str:
        """Prompt for phase-aware conversational cues."""
        pkg = assessment["package"]
        
        if not is_mature:
            return f"""
KULLANICI PROFİLİ (Henüz Eksik):
- Meslek: {profile.profession or 'Belirsiz'}
- Yaşadığı Şehir: {profile.hometown or 'Belirsiz'}
- Medeni Durum: {profile.marital_status or 'Belirsiz'}

KONUŞMA AŞAMASI: TANIŞMA VE YAŞAM TARZI (LIFESTYLE DISCOVERY)

GÖREV:
Bu kullanıcıyla tanışmaya devam edecek, samimi ve bilgece bir 'sohbete giriş' veya 'ilgi gösterme' cümlesi üret.
- ASLA evlerden, bütçeden, paketlerden veya "bir tık yatırım" gibi satış ifadelerinden bahsetme.
- Sadece kullanıcının yaşam tarzını, alışkanlıklarını veya hayata bakışını anlamaya odaklan.
- "Sizin gibi vizyon sahibi biri..." gibi nazik bir ton kullan ama mülk tanıtımı yapma.
- Yanıt sadece 1 cümle olsun.
"""

        upgrade_text = "Kullanıcı bir üst segmente yakın, onu çok hafifçe ve doğal bir şekilde yukarıya (yatırım değeri veya prestij vurgusuyla) teşvik et." if assessment["is_near_upgrade"] else ""
        
        return f"""
KULLANICI PROFİLİ:
- Meslek: {profile.profession or 'Belirsiz'}
- Maaş: {profile.estimated_salary or 'Belirsiz'}
- Medeni Durum: {profile.marital_status or 'Belirsiz'}
- Hobiler: {', '.join(profile.hobbies) if profile.hobbies else 'Belirsiz'}

KONUŞMA AŞAMASI: SEGMENT YÖNLENDİRME (STRATEGIC GUIDANCE)

ANALİZİMİZ:
- SEGMENT: {assessment['tier']} Paketi ({pkg['range']})
- ODAK NOKTASI: {pkg['focus']}
- MOTİVASYON: {assessment['motivation']}
- {upgrade_text}

GÖREV:
Bu kullanıcıyı hissettirmeden {assessment['tier']} segmentindeki bir yaşama yönlendirecek NET ve SONUÇ ODAKLI bir öneri cümlesi üret.
- Cümle doğal ama profesyonel olsun.
- "A segmenti size uygun" gibi teknik ifadeler kullanma.
- "Sizin gibi vizyon sahibi..." gibi iltifatlar YASAK.
- Örnek: "Bütçe ve yaşam standartlarınız göz önüne alındığında B grubu projelerimizdeki geniş daireler beklentinizi tam karşılayacaktır."
- Yanıt sadece 1 cümle olsun.
"""

    def _fallback_guidance(self, user_profile: UserProfile) -> dict:
        """Safe fallback strategy."""
        return {
            "tier": "A",
            "package_info": {"range": "7-9M TL", "focus": "Essential living"},
            "guidance_cue": "Yaşam tarzınızdaki bu detaylar, aslında sizin için en huzurlu alanın ipuçlarını veriyor.",
            "motivation": "Temel analiz",
            "is_near_upgrade": False,
            "is_profile_mature": False,
            "conversation_hooks": []
        }
