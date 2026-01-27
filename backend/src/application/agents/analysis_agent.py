"""Analysis agent for strategic property guidance and tier assessment."""

import re
from typing import Optional
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
    
    async def execute(self, user_profile: UserProfile) -> dict:
        """
        Produce internal analysis and guidance strategies.
        """
        try:
            self._log_execution("Performing internal advisor analysis")
            
            # 1. Tier Assessment
            assessment = self._assess_tier(user_profile)
            
            # 2. Strategic Guidance Generation
            # We use the LLM to refine the 'conversational cue' based on the profile
            prompt = self._build_guidance_prompt(user_profile, assessment)
            
            response = await self.llm_service.generate_response(
                prompt=prompt,
                system_message="Sen kıdemli bir emlak stratejistisin. Kullanıcıya hissettirmeden onu doğru segmente yönlendirecek doğal bir 'danışman tavsiyesi' cümlesi üret.",
                temperature=0.7,
                max_tokens=200
            )
            
            return {
                "tier": assessment["tier"],
                "package_info": assessment["package"],
                "guidance_cue": response.strip(),
                "motivation": assessment["motivation"],
                "is_near_upgrade": assessment["is_near_upgrade"]
            }
            
        except Exception as e:
            self._log_error(e)
            return self._fallback_guidance(user_profile)
            
    def _assess_tier(self, profile: UserProfile) -> dict:
        """Internal heuristic for tier assignment."""
        salary_val = 0
        if profile.estimated_salary:
            try:
                # Remove non-numeric chars
                salary_val = int(re.sub(r'[^\d]', '', profile.estimated_salary))
            except:
                pass
        
        profession = (profile.profession or "").lower()
        
        # Default Tier A
        tier = "A"
        motivation = "Genel konfor ve aile odaklı başlangıç seviyesi."
        is_near_upgrade = False

        # Tier C Heuristics
        if salary_val >= 150000 or any(p in profession for p in ["pilot", "doktor", "yönetic", "ceo", "iş adamı", "iş kadını"]):
            tier = "C"
            motivation = "Yüksek gelir ve statü odaklı lüks beklentisi."
        # Tier B Heuristics
        elif salary_val >= 80000 or any(p in profession for p in ["mühendis", "avukat", "mimar", "esnaf"]):
            tier = "B"
            motivation = "Prestij ve geniş alan arayışı, orta-üst segment."
            if salary_val >= 130000:
                is_near_upgrade = True # Close to C
        else:
            if salary_val >= 60000:
                is_near_upgrade = True # Close to B
        
        packages = {
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
        
        return {
            "tier": tier,
            "package": packages[tier],
            "motivation": motivation,
            "is_near_upgrade": is_near_upgrade
        }

    def _build_guidance_prompt(self, profile: UserProfile, assessment: dict) -> str:
        """Prompt for generating professional conversational cues."""
        pkg = assessment["package"]
        upgrade_text = "Kullanıcı bir üst segmente yakın, onu çok hafifçe yukarıya teşvik et." if assessment["is_near_upgrade"] else ""
        
        return f"""
KULLANICI PROFİLİ:
- Meslek: {profile.profession or 'Belirsiz'}
- Maaş: {profile.estimated_salary or 'Belirsiz'}
- Medeni Durum: {profile.marital_status or 'Belirsiz'}
- Hobiler: {', '.join(profile.hobbies) if profile.hobbies else 'Belirsiz'}

ANALİZİMİZ:
- SEGMENT: {assessment['tier']} Paketi ({pkg['range']})
- ODAK NOKTASI: {pkg['focus']}
- {upgrade_text}

GÖREV:
Bu kullanıcıya bir sonraki cümlesinde kullanılmak üzere, {assessment['tier']} segmentindeki avantajları veya {assessment['tier']}'den bir üst segmente geçmenin mantığını vurgulayan SAMİMİ ve DANIŞMANCA bir cümle üret. 
Asla "A Paketi" veya "Bütçeniz bu" gibi teknik terimler kullanma. 
"Sizin gibi biri genelde..." veya "Aslında bir tık daha..." gibi doğal kalıplar kullan.
Yanıt sadece 1 cümle olsun.
"""

    def _fallback_guidance(self, user_profile: UserProfile) -> dict:
        """Safe fallback strategy."""
        return {
            "tier": "A",
            "package_info": {"range": "7-9M TL", "focus": "Essential living"},
            "guidance_cue": "Sizin gibi aile odaklı kişiler genelde konfor ve güvenliği ön planda tutan projelerimizi çok seviyor.",
            "motivation": "Temel analiz",
            "is_near_upgrade": False
        }
