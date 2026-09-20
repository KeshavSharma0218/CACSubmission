import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

SUPABASE_URL = "postgresql+asyncpg://postgres.pqqfjboeoykcnluomwhz:Krishna021802187391@aws-0-us-east-1.pooler.supabase.com:5432/postgres"

async def check():
    engine = create_async_engine(SUPABASE_URL, connect_args={"ssl": "require"})
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
    
    await engine.dispose()

asyncio.run(check())
