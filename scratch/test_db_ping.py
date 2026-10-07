import asyncio
from app.db.session import AsyncSessionLocal
from sqlalchemy import text

async def check():
    try:
        async with AsyncSessionLocal() as s:
            res = await s.execute(text("SELECT count(*) FROM rooms;"))
            count = res.scalar()
            print("DB ROOMS COUNT:", count)
            res2 = await s.execute(text("SELECT id, name FROM rooms;"))
            for r in res2.fetchall():
                print("  Room:", r[0], r[1])
    except Exception as e:
        print("DB ERROR:", e)

if __name__ == "__main__":
    asyncio.run(check())
