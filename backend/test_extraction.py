"""
Test script to reproduce the error and capture logs.
Run this to see the actual error message.
"""

import asyncio
import sys
sys.path.append('src')

from infrastructure.llm.langchain_service import LangChainService
from infrastructure.llm.information_extractor import InformationExtractor

async def test_extraction():
    print("Testing information extraction with deepseek-thinking model...")
    
    llm_service = LangChainService()
    extractor = InformationExtractor(llm_service)
    
    message = "ilayda inal"
    history = ""
    
    try:
        result = await extractor.extract_profile_info(message, history)
        print("✅ SUCCESS!")
        print(f"Result: {result}")
    except Exception as e:
        print(f"❌ ERROR: {type(e).__name__}: {str(e)}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_extraction())
