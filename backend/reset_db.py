"""
Database Reset Script
Run this to drop all tables and rebuild the schema fresh.
"""

import asyncio
import sys
sys.path.append('src')

from infrastructure.database.session import engine, Base
from infrastructure.config import get_logger

logger = get_logger(__name__)

async def reset_database():
    """Drop all tables and recreate them."""
    try:
        logger.info("🔥 Dropping all tables...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        logger.info("✅ All tables dropped")
        
        logger.info("🏗️ Creating fresh tables...")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("✅ Fresh database ready!")
        
    except Exception as e:
        logger.error(f"❌ Error: {e}")
        raise
    finally:
        await engine.dispose()

if __name__ == "__main__":
    print("\n⚠️  WARNING: This will DELETE ALL DATA in the database!\n")
    response = input("Are you sure? Type 'yes' to continue: ")
    
    if response.lower() == 'yes':
        asyncio.run(reset_database())
        print("\n✅ Database has been reset successfully!\n")
    else:
        print("\n❌ Cancelled.\n")
