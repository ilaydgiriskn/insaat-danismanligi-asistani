import asyncio
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from infrastructure.database.session import get_engine, Base, init_db
from infrastructure.config import get_settings

async def reset_database():
    print("Veritabanı şeması güncelleniyor...")
    engine = get_engine()
    settings = get_settings()
    print(f"Bağlanılan adres: {settings.database_url}")
    
    async with engine.begin() as conn:
        print("Mevcut tablolar siliniyor...")
        await conn.run_sync(Base.metadata.drop_all)
        print("Yeni tablolar oluşturuluyor...")
        await conn.run_sync(Base.metadata.create_all)
    
    print("✅ İşlem tamamlandı! Veritabanı yeni alanlarla (email, meslek, hobiler vb.) hazır.")

if __name__ == "__main__":
    asyncio.run(reset_database())
