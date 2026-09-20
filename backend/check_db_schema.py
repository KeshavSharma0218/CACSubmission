import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text

# This will use the DATABASE_URL from .env
import os
from dotenv import load_dotenv
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    print("No DATABASE_URL in .env")
    exit(1)

# Fix for asyncpg SSL
if "supabase.co" in DATABASE_URL and "sslmode=" in DATABASE_URL:
    DATABASE_URL = DATABASE_URL.split("?")[0]

engine = create_async_engine(DATABASE_URL, connect_args={"ssl": "require"} if "supabase.co" in DATABASE_URL else {})

async def check():
    async with engine.connect() as conn:
        tables = ["safe_walk_sessions", "user_reports", "users", "trusted_contacts"]
        for table in tables:
            result = await conn.execute(text(f"""
                SELECT column_name, data_type, udt_name
                FROM information_schema.columns 
                WHERE table_name = '{table}' 
                ORDER BY ordinal_position
            """))
            print(f"\n=== {table} ===")
            for row in result:
                print(f"  {row[0]}: {row[1]} ({row[2]})")
        
        # Check enum types
        result = await conn.execute(text("""
            SELECT typname, enumlabel 
            FROM pg_enum 
            JOIN pg_type ON pg_enum.enumtypid = pg_type.oid
            ORDER BY typname, enumsortorder
        """))
        print("\n=== enum types ===")
        current_type = None
        for row in result:
            if row[0] != current_type:
                current_type = row[0]
                print(f"  {current_type}:")
            print(f"    - {row[1]}")

    await engine.dispose()

asyncio.run(check())
