import asyncio
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import inspect

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@postgres:5432/interstellar_mare")

async def inspect_schema():
    print(f"Connecting to {DATABASE_URL}...")
    engine = create_async_engine(DATABASE_URL)
    
    async with engine.connect() as conn:
        # Check columns in user_profiles
        print("\n--- Columns in user_profiles ---")
        result = await conn.execute(text("SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name = 'user_profiles';"))
        rows = result.fetchall()
        for row in rows:
            print(f"- {row.column_name} ({row.data_type}, Nullable: {row.is_nullable})")
            
        if not rows:
            print("WARNING: user_profiles table not found!")

    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(inspect_schema())
