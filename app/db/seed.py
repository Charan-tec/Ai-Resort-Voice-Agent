import asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.logging import logger
from app.db.models import Room
from app.db.session import AsyncSessionLocal, engine
INITIAL_ROOMS = [
    {
        "room_id": "villa-ocean-101",
        "name": "Oceanfront Luxury Villa",
        "room_type": "villa",
        "max_occupancy": 4,
        "base_rate_nightly": 650.0,
        "amenities": ["Private Infinity Pool", "Ocean View", "King Bed", "Butler Service", "Complimentary Breakfast"]
    },
    {
        "room_id": "suite-deluxe-201",
        "name": "Deluxe Sunset Suite",
        "room_type": "suite",
        "max_occupancy": 2,
        "base_rate_nightly": 380.0,
        "amenities": ["Panoramic Sunset Balcony", "King Bed", "Whirlpool Spa Tub", "Espresso Bar"]
    },
    {
        "room_id": "bungalow-garden-301",
        "name": "Garden Tropical Bungalow",
        "room_type": "bungalow",
        "max_occupancy": 3,
        "base_rate_nightly": 290.0,
        "amenities": ["Private Zen Garden", "Rain Shower", "Queen Bed", "Hammock Terrace"]
    },
    {
        "room_id": "suite-presidential-401",
        "name": "Presidential Ocean Suite",
        "room_type": "suite",
        "max_occupancy": 4,
        "base_rate_nightly": 850.0,
        "amenities": ["Panoramic Ocean Terrace", "Master King Bedroom", "Whirlpool Spa Tub", "Dedicated Butler Service", "Complimentary Champagne"]
    },
    {
        "room_id": "villa-family-501",
        "name": "Family Pool Villa",
        "room_type": "villa",
        "max_occupancy": 6,
        "base_rate_nightly": 520.0,
        "amenities": ["Private Swimming Pool", "Sun Deck & Garden", "Two King Beds & Bunk Suite", "Full Kitchenette", "Family Entertainment Center"]
    },
    {
        "room_id": "suite-premium-302",
        "name": "Premium Garden Suite",
        "room_type": "suite",
        "max_occupancy": 3,
        "base_rate_nightly": 450.0,
        "amenities": ["Tropical Garden View", "King Bed & Daybed", "Marble Soaking Tub", "Espresso Bar", "Complimentary Breakfast"]
    }
]


async def seed_rooms(session: AsyncSession):
    """Seed initial luxury inventory into PostgreSQL rooms table idempotently."""
    logger.info("Seeding resort rooms...")
    for r_data in INITIAL_ROOMS:
        existing = await session.get(Room, r_data["room_id"])
        if not existing:
            room = Room(
                id=r_data["room_id"],
                name=r_data["name"],
                room_type=r_data["room_type"],
                max_occupancy=r_data["max_occupancy"],
                base_rate=r_data["base_rate_nightly"],
                amenities=r_data.get("amenities", []),
                is_active=True
            )
            session.add(room)
            logger.info(f"Added room: {r_data['name']} ({r_data['room_id']})")
        else:
            existing.name = r_data["name"]
            existing.room_type = r_data["room_type"]
            existing.max_occupancy = r_data["max_occupancy"]
            existing.base_rate = r_data["base_rate_nightly"]
            if not existing.amenities:
                existing.amenities = r_data.get("amenities", [])
    await session.commit()
    logger.info("Room seeding completed.")


async def main():
    async with AsyncSessionLocal() as session:
        await seed_rooms(session)
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
