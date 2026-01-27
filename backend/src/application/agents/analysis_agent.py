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
            is_profile_mature = bool(user_profile.name and (user_profile.profession or user_profile.hometown))
            assessment = self._assess_tier(user_profile)
            
            # 2. Strategic Guidance Generation
            # If profile isn't mature, focus on lifestyle/introduction, not house segments.
            prompt = self._build_guidance_prompt(user_profile, assessment, is_mature=is_profile_mature)
            
            response = await self.llm_service.generate_response(
                prompt=prompt,
                system_message="Sen kıdemli bir emlak stratejistisin. Kullanıcıyla tanışma aşamasında isen onu tanımaya yönelik, tanışma bitti ise onu doğru segmente yönlendirecek doğal bir cümle üret.",
                temperature=0.7,
                max_tokens=200
            )
            
            return {
                "tier": assessment["tier"] if is_profile_mature else "Discovery",
                "package_info": assessment["package"] if is_profile_mature else {},
                "guidance_cue": response.strip(),
                "motivation": assessment["motivation"],
                "is_near_upgrade": assessment["is_near_upgrade"] if is_profile_mature else False,
                "is_profile_mature": is_profile_mature
            }
            
        except Exception as e:
            self._log_error(e)
            return self._fallback_guidance(user_profile)
            
    def _assess_tier(self, profile: UserProfile) -> dict:
        """Internal heuristic for tier assignment with risk appetite and motivation."""
        salary_val = 0
        if profile.estimated_salary:
            try:
                # Remove non-numeric chars
                salary_val = int(re.sub(r'[^\d]', '', profile.estimated_salary))
            except:
                pass
        
        profession = (profile.profession or "").lower()
        marital_status = (profile.marital_status or "").lower()
        
        # Default Tier A
        tier = "A"
        motivation = "Yaşam konforu ve başlangıç seviyesi bir yatırım."
        is_near_upgrade = False

        # Tier C Heuristics (High potential or status)
        if salary_val >= 150000 or any(p in profession for p in ["pilot", "doktor", "yönetic", "ceo", "iş adamı", "iş kadını", "mimar"]):
            tier = "C"
            motivation = "Lüks, özel tasarım ve yüksek yatırım potansiyeli."
        # Tier B Heuristics (Established professional)
        elif salary_val >= 80000 or any(p in profession for p in ["mühendis", "avukat", "esnaf", "yazılımcı"]):
            tier = "B"
            motivation = "Prestij, geniş sosyal donatı ve modern yaşam."
            if salary_val >= 130000 or marital_status == "evli":
                is_near_upgrade = True # Close to C/Higher value
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
Bu kullanıcıyı hissettirmeden {assessment['tier']} segmentindeki bir yaşama veya {assessment['tier']}'den bir üst segmente geçmenin avantajlarına yönlendirecek BİLGECE bir tavsiye cümlesi üret.
- Cümle doğal bir sohbetin parçası gibi olmalı.
- "A segmenti size uygun" gibi teknik ifadelerden veya "bir tık yatırım" gibi itici kalıplardan KAÇIN.
- "Aslında şu yöne bir tık daha pay ayırmak seçenekleri ciddi genişletiyor..." gibi (eğer upgrade yakınsa) veya "Sizin gibi aile odaklı bir hayat isteyenler genelde bu tarz..." gibi cümleler kur.
- Yanıt sadece 1 cümle olsun.
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
