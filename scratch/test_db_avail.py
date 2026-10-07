import asyncio
from app.tools.availability import check_availability

async def main():
    cases = [
        ("2026-11-21", "2026-11-25", 2),
        ("2027-01-10", "2027-01-15", 2),
        ("2027-11-21", "2027-11-25", 2),
        ("2030-11-21", "2030-11-25", 2),
        ("2027-12-28", "2028-01-03", 2),
        ("2028-02-28", "2028-03-02", 2),
        ("2027-02-29", "2027-03-02", 2),
        ("2026-11-25", "2026-11-21", 2),
    ]

    for ci, co, g in cases:
        res = await check_availability(check_in=ci, check_out=co, guests=g)
        print(f"check_availability(ci={ci}, co={co}, guests={g}):")
        print(f"  ok={res.get('ok')}, available={res.get('available')}, count={res.get('count')}, err={res.get('error')}")
        if res.get('available_rooms'):
            print(f"  rooms={[r['name'] for r in res['available_rooms']]}")
        print()

if __name__ == "__main__":
    asyncio.run(main())
