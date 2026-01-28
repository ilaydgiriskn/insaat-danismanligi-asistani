import asyncio
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@postgres:5432/interstellar_mare")

async def apply_fix():
    print(f"Connecting to {DATABASE_URL}...")
    engine = create_async_engine(DATABASE_URL)
    
    # Missing columns for user_profiles
    user_cols = [
        ("email", "character varying(255)"),
        ("phone_number", "character varying(50)"),
        ("hometown", "character varying(255)"),
        ("profession", "character varying(255)"),
        ("marital_status", "character varying(50)"),
        ("has_children", "boolean"),
        ("estimated_salary", "character varying(255)"),
        ("hobbies", "json"),
        ("surname", "character varying(255)"),
        ("current_city", "character varying(255)"),
        ("lifestyle_notes", "character varying"),
    ]
    
    async with engine.begin() as conn:
        for col, col_type in user_cols:
            try:
                await conn.execute(text(f"ALTER TABLE user_profiles ADD COLUMN IF NOT EXISTS {col} {col_type};"))
                print(f"✓ Column {col} in user_profiles verified.")
            except Exception as e:
                print(f"Error for {col}: {e}")
                
        # Handle message_metadata rename if necessary
        try:
            # Check if metadata exists and message_metadata does not
            res = await conn.execute(text("SELECT column_name FROM information_schema.columns WHERE table_name='messages' AND column_name='metadata';"))
            if res.scalar():
                await conn.execute(text("ALTER TABLE messages RENAME COLUMN metadata TO message_metadata;"))
                print("✓ Renamed metadata to message_metadata in messages table.")
        except:
            pass
            
    print("\n--- SCHEMA VERIFIED ---")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(apply_fix())
