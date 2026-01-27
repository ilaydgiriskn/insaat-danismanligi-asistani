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
            # Profile is mature only if we have: Name, Profession/Hometown, Marital Status AND Hobbies
            is_profile_mature = user_profile.is_complete()
            assessment = self._assess_tier(user_profile)
            
            # 2. Strategic Guidance Generation
            # If profile isn't mature, focus on lifestyle/introduction, not house segments.
            prompt = self._build_guidance_prompt(user_profile, assessment, is_mature=is_profile_mature)
            
            response = await self.llm_service.generate_response(
                prompt=prompt,
                system_message="Sen kıdemli bir emlak stratejistisin. İnsan psikolojisinden iyi anlıyorsun. Tanışma aşamasında isen sadece kullanıcıyı tanımaya yönelik, tanışma bitti ise onu doğru segmente (A, B, C) çekmeye yönelik samimi bir cümle üret.",
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
            
    async def generate_full_analysis(self, user_profile: UserProfile) -> str:
        """
        Final phase: Generate a comprehensive, personalized property recommendation.
        """
        try:
            assessment = self._assess_tier(user_profile)
            pkg = assessment["package"]
            
            prompt = f"""
KULLANICI PROFİLİ:
- İsim: {user_profile.name}
- Meslek: {user_profile.profession}
- Lokasyon: {user_profile.location.city if user_profile.location else user_profile.hometown}
- Medeni Durum: {user_profile.marital_status}
- Hobiler: {', '.join(user_profile.hobbies)}
- Bütçe: {user_profile.budget.max_amount if user_profile.budget else 'Belirsiz'} TL

SEÇİLEN SEGMENT: {assessment['tier']} Paketi ({pkg['range']})
SEGMENT ODAĞI: {pkg['focus']}

GÖREV:
Bu kullanıcıya özel, samimi, bilgece ve heyecan verici bir "Final Önerisi" hazırla.
- Kullanıcıya ismen hitap et.
- Neden bu segmentin (A, B veya C) ona çok uygun olduğunu, hobilerine ve yaşam tarzına atıfta bulunarak açıkla.
- "X paketi size uygun" gibi soğuk terimler yerine, "Sizin için seçtiğim bu yaşam konsepti..." gibi sahiplenici bir dil kullan.
- Evin artılarını (bahçe, oda sayısı, konum) onun hayalleriyle birleştir.
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
