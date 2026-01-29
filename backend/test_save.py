import asyncio
import os
import sys

# Add src to path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from domain.entities import UserProfile
from infrastructure.database.models import UserModel
from infrastructure.database.repositories import SQLAlchemyUserRepository
from infrastructure.database.session import Base

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@postgres:5432/interstellar_mare")

async def test_save():
    print(f"Connecting to {DATABASE_URL}...")
    engine = create_async_engine(DATABASE_URL)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    
    async with async_session() as session:
        repo = SQLAlchemyUserRepository(session)
        
        print("Creating dummy profile...")
        profile = UserProfile(name="Test", surname="User")
        # Ensure consistency with what might happen in app
        profile.social_amenities = [] 
        # profile.social_amenities = None # Uncomment to test failure logic manually if needed
        
        try:
            print("Attempting to save...")
            saved_profile = await repo.create(profile)
            print(f"SUCCESS! Saved profile ID: {saved_profile.id}")
            print(f"Social Amenities: {saved_profile.social_amenities}")
        except Exception as e:
            print(f"FAILURE! Error: {e}")
            import traceback
            traceback.print_exc()

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(test_save())
