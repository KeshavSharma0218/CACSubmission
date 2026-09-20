import asyncio
from app.database.database import engine
from sqlalchemy import text

async def check():
    async with engine.connect() as conn:
        # Check safe_walk_sessions columns
        result = await conn.execute(text("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'safe_walk_sessions' 
            ORDER BY ordinal_position
        """))
        print("=== safe_walk_sessions ===")
        for row in result:
            print(f"  {row[0]}: {row[1]}")
        
        # Check user_reports columns
        result = await conn.execute(text("""
            SELECT column_name, data_type 
            FROM information_schema.columns 
            WHERE table_name = 'user_reports' 
            ORDER BY ordinal_position
        """))
        print("\n=== user_reports ===")
        for row in result:
            print(f"  {row[0]}: {row[1]}")

asyncio.run(check())
