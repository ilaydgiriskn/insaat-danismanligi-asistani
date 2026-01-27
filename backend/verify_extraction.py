import asyncio
import sys
import os

# Add backend/src to path
sys.path.append(os.path.join(os.getcwd(), 'backend', 'src'))

from infrastructure.llm import LangChainService, InformationExtractor
from infrastructure.config import get_settings

async def test_contextual_extraction():
    print("Testing contextual extraction...")
    llm_service = LangChainService()
    extractor = InformationExtractor(llm_service)
    
    # Test case: Yes/No answer with context
    message = "Evet"
    history = "Asistan: Çocuğunuz var mı?\nKullanıcı: Merhaba"
    
    print(f"Message: {message}")
    print(f"History context:\n{history}")
    
    result = await extractor.extract_profile_info(message, history)
    
    print("\nExtraction Result:")
    import json
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    if result.get('has_children') is True:
        print("\n✅ SUCCESS: Contextual has_children extraction works!")
    else:
        print("\n❌ FAILED: has_children not extracted correctly.")

    # Test case: Profession to salary inference
    message = "Doktorum"
    result = await extractor.extract_profile_info(message, "")
    print("\nExtraction Result for 'Doktorum':")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    if result.get('estimated_salary_range'):
        print(f"\n✅ SUCCESS: Salary inference works: {result.get('estimated_salary_range')}")
    else:
        print("\n❌ FAILED: Salary inference missing.")

if __name__ == "__main__":
    asyncio.run(test_contextual_extraction())
