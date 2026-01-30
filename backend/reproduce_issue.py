
import asyncio
import sys
import json

# Add backend to path
sys.path.append('/app/src')

from infrastructure.llm.information_extractor import InformationExtractor
from infrastructure.llm.langchain_service import LangChainService
from infrastructure.config.settings import get_settings

async def main():
    print("Testing Information Extraction for User Report...")
    
    settings = get_settings()
    llm_service = LangChainService()
    extractor = InformationExtractor(llm_service)
    
    # 1. Test Room Extraction
    message_rooms = "3 oda istiyorum ama odalar cok dar olmasın"
    history_rooms = """Asistan: Kaç oda?
Kullanıcı: 3 oda"""
    
    print(f"\n--- Testing Rooms: '{message_rooms}' ---")
    result_rooms = await extractor.extract_profile_info(message_rooms, history_rooms)
    print(json.dumps(result_rooms, indent=2, ensure_ascii=False))

    # 2. Test Social Amenities
    message_social = "havuza her sabah girmek isterim. yuruyus parkuru bir de cocuk parkı benim için iyidir"
    history_social = """Asistan: Sosyal alan?
Kullanıcı: Havuz"""
    
    # 3. Test Sequential Overwrite
    print(f"\n--- Testing Overwrite Hypothesis ---")
    message_seq1 = "3 oda ve havuz istiyorum"
    history_seq1 = ""
    result1 = await extractor.extract_profile_info(message_seq1, history_seq1)
    print("Msg 1 (Set values):", json.dumps({k:v for k,v in result1.items() if k in ['rooms', 'social_amenities']}, ensure_ascii=False))
    
    message_seq2 = "bekarım ama nisanlanacagım"
    history_seq2 = "Asistan: Oda? Kullanıcı: 3 oda. Asistan: Medeni durum? Kullanıcı: bekar"
    result2 = await extractor.extract_profile_info(message_seq2, history_seq2)
    print("Msg 2 (Unrelated):", json.dumps({k:v for k,v in result2.items() if k in ['rooms', 'social_amenities']}, ensure_ascii=False))
