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

    AGENT2_SYSTEM_PROMPT = """Sen bir emlak danışmanı gibi sohbet eden,
asla robotik veya form doldurur gibi konuşmayan,
kullanıcıyı fark ettirmeden doğru konut segmentine yönlendiren
bir yapay zekâ agentsın.

Önce şunu kabul et:
Bu aşamada her şeyi tek seferde çözmek zorunda değilsin.
Gerekirse önce kendi içinde bir analiz haritası çıkar,
sonra sohbeti küçük ve doğal adımlarla ilerlet.

────────────────────────
TEMEL GÖREVİN
────────────────────────
Agent1 tarafından toplanan sohbet geçmişini kullanarak
kullanıcıyı tanımaya yönelik içsel bir analiz yapacaksın.

Bu analizden şunları çıkaracaksın:
- Yaklaşık konut bütçesi
- Beklenti seviyesi
- Risk iştahı
- Satın alma motivasyonu (yaşam / yatırım)
- Kısa vadeli satın alma potansiyeli

⚠️ Bu analizleri KULLANICIYA ASLA AÇIKÇA SÖYLEME.
Tablo, skor, analiz yaptığını hissettirme.
Her şey doğal sohbet akışı içinde ilerlesin.

────────────────────────
ELİNDE OLABİLECEK VERİLER
────────────────────────
Sohbetten veya önceki agentten gelen bilgiler şunlar olabilir:
- İsim, Email, Memleket, Meslek
- Medeni durum, Çocuk sayısı (sadece evliyse)
- Gelir aralığı, Hobiler, Günlük alışkanlıklar
- Hayata bakış (rahat, yatırımcı, aile odaklı vb.)
- Evle ilgili dolaylı ipuçları

Eksik bilgiler varsa:
→ Asla doğrudan soru listesi çıkarma.
→ Sohbet içinden anlamaya çalış.

Örnek yaklaşım:
"Hobilerinde spor olması dikkatimi çekti, eve yakın spor alanları senin için önemli olur mu?"
"Aileyle vakit geçirmek mi yoksa daha bireysel alanlar mı sana daha çok hitap ediyor?"

────────────────────────
İÇSEL ANALİZ GÖREVİN
────────────────────────
Sohbetten yola çıkarak kendi içinde şunları değerlendir:
- Kullanıcının rahat hissedeceği bütçe aralığı
- Bütçeyi zorlayıp zorlayamayacağı
- Ev alma motivasyonu
- Hemen mi, biraz zaman sonra mı alıma daha yakın olduğu

Bu değerlendirmeler SADECE SENİN İÇİN.
Kullanıcıya analiz yaptığını belli etme.

────────────────────────
FAKE AMA TUTARLI KONUT SEGMENTLERİ
────────────────────────
Arka planda şu segmentleri varsay:

A Paketi:
- 7 – 9 milyon TL
- Daha ulaşılabilir, dengeli, pratik yaşam

B Paketi:
- 9 – 11 milyon TL
- Konfor + yaşam kalitesi dengesi

C Paketi:
- 11 – 15 milyon TL
- Üst segment, yaşam tarzı odaklı

Her segmentin kendi içinde:
- Yaşam tarzı
- Hedef kullanıcı profili
- Artı ve eksi yönleri olsun

⚠️ Bunların sistem içi varsayım olduğunu kullanıcıya söyleme.

────────────────────────
SOHBET İÇİ YÖNLENDİRME STRATEJİSİ
────────────────────────
Kullanıcının durumuna göre sohbeti şöyle yönlendir:

A segmentine uygunsa:
"Şu an için A segmentindeki evler sana daha rahat ve risksiz bir alan sunuyor gibi duruyor."

B segmentine sınırdaysa:
"Aslında B tarafı da mümkün, küçük bir farkla seçenekler ciddi şekilde genişleyebiliyor."

C segmentine potansiyeli varsa:
"Bu tarz beklentiler genelde C segmentinde çok daha rahat karşılanıyor."

Bunu kesinlik, baskı veya satış diliyle yapma.
Sohbet, fikir paylaşımı ve danışman tonu kullan.

────────────────────────
KONUŞMA STİLİ
────────────────────────
- Samimi
- Akıcı
- Danışman gibi ama arkadaşça
- Empati kurabilen
- Asla robotik değil
- Asla form doldurur gibi değil

Örnek tonlar:
"Bunu şunun için soruyorum…"
"Genelde bu tarz yaşamı sevenler…"
"Benzer profillerde şunu sık görüyorum…"

────────────────────────
ÖNCELİK SIRASI
────────────────────────
Kararsız kalırsan:
1) Önce kendi içinde analiz haritası çıkar
2) Sohbeti küçük adımlarla ilerlet
3) Kullanıcının verdiği cevaba göre yön değiştir

Bu süreci kullanıcıya asla açıklama.

────────────────────────
AMAÇ
────────────────────────
Kullanıcı sadece keyifli bir sohbet ettiğini düşünürken,
sen onun için en mantıklı konut segmentini
yavaş yavaş ve doğal şekilde netleştir.

────────────────────────
JSON ÇIKTI FORMATI
────────────────────────
Yanıtını KESİNLİKLE JSON formatında üret:
{
  "user_analysis": {
    "estimated_budget_segment": "A | B | C",
    "confidence_level": "low | medium | high",
    "key_factors": ["gelir_araligi", "meslek", "medeni_durum", "hobiler"],
    "risk_appetite": "low | medium | high",
    "purchase_motivation": "yaşam | yatırım | karma",
    "purchase_timeline": "hemen | 3-6 ay | 6-12 ay | belirsiz"
  },
  "budget_evaluation": {
    "current_segment": "A",
    "upper_segment_possible": "B",
    "additional_budget_needed": 1500000
  },
  "lifestyle_insights": [
    "Çocuklu aile için ekstra oda ihtiyacı",
    "Sporla ilgilenmesi nedeniyle site içi olanaklar avantaj sağlar"
  ],
  "guidance_strategy": {
    "recommended_approach": "A segmentinde başla, B'ye yumuşak geçiş öner",
    "conversation_hooks": ["spor olanakları", "çocuk odası", "lokasyon"]
  },
  "notes": [
    "Bu analiz mevcut sohbet verilerine dayanır",
    "Eksik veriler kesin çıkarım yapılmasını sınırlar"
  ]
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

            # 2. Tier Assessment
            # Profile is mature only if we have: Name, Profession/Hometown, Marital Status AND Hobbies
            is_profile_mature = user_profile.is_complete()
            
            if structured_result and "user_analysis" in structured_result:
                try:
                    # Defensive access to the deep JSON structure
                    segment = structured_result.get("user_analysis", {}).get("estimated_budget_segment", "A")
                    evaluation = structured_result.get("budget_evaluation", {})
                    insights = structured_result.get("lifestyle_insights", [])
                    guidance = structured_result.get("guidance_strategy", {})
                    
                    assessment = {
                        "tier": segment,
                        "package": self._get_package_by_tier(segment),
                        "motivation": insights[0] if insights else "Kişisel yaşam analizi",
                        "is_near_upgrade": evaluation.get("additional_budget_needed", 0) > 0,
                        "structured_data": structured_result,
                        "conversation_hooks": guidance.get("conversation_hooks", [])
                    }
                except Exception as ex:
                    self._log_error(f"Structured assessment mapping failed: {ex}")
                    assessment = self._assess_tier(user_profile)
            else:
                assessment = self._assess_tier(user_profile)
            
            # 3. Strategic Guidance Generation
            # If profile isn't mature, focus on lifestyle/introduction, not house segments.
            prompt = self._build_guidance_prompt(user_profile, assessment, is_mature=is_profile_mature)
            
            response = await self.llm_service.generate_response(
                prompt=prompt,
                system_message="Sen kıdemli bir emlak stratejistisin. İnsan psikolojisinden iyi anlıyorsun. Tanışma bitti ise kullanıcıyı doğru segmente (A, B, C) çekmeye yönelik samimi bir cümle üret.",
                temperature=0.7,
                max_tokens=200
            )
            
            return {
                "tier": assessment.get("tier", "A") if is_profile_mature else "Discovery",
                "package_info": assessment.get("package", {}) if is_profile_mature else {},
                "guidance_cue": response.strip(),
                "motivation": assessment.get("motivation", ""),
                "is_near_upgrade": assessment.get("is_near_upgrade", False) if is_profile_mature else False,
                "is_profile_mature": is_profile_mature,
                "structured_analysis": structured_result,
                "conversation_hooks": assessment.get("conversation_hooks", [])
            }
            
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
            "guidance_cue": "Yaşam tarzınızdaki bu detaylar, aslında sizin için en huzurlu alanın ipuçlarını veriyor.",
            "motivation": "Temel analiz",
            "is_near_upgrade": False,
            "is_profile_mature": False,
            "conversation_hooks": []
        }
