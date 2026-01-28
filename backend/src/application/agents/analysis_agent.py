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

GÖREVLERİN:
1. Kullanıcının geçmiş sohbetini analiz et: Bütçe potansiyeli nedir?
2. Sohbet akışını doğal bir şekilde devam ettirecek, sıcak bir YÖNLENDİRME cümlesi kur.
3. Asla "Sizi B paketine aldık" deme. "Sizin gibi konfora düşkünler için harika seçeneklerimiz var" de.

Yanıtını KESİNLİKLE JSON formatında üret:
{
  "user_analysis": {
    "estimated_budget_segment": "A | B | C",
    "risk_appetite": "low | medium | high",
    "key_factors": ["meslek", "maaş", "lokasyon"]
  },
  "guidance_message": "Kullanıcıya söyleyeceğin o samimi, yönlendirici ve doğal cümle."
}"""

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
                max_tokens=1000
            )

            # Cleanup potential markdown artifacts
            clean_json = response.strip()
            if "```json" in clean_json:
                clean_json = clean_json.split("```json")[1].split("```")[0].strip()
            elif "```" in clean_json:
                clean_json = clean_json.split("```")[1].split("```")[0].strip()
                
            return json.loads(clean_json)
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
