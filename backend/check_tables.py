import asyncio
from app.database.database import engine
from sqlalchemy import text

async def check():
    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name"))
        for row in result:
            print(row[0])

asyncio.run(check())
