"""Data seeding script — CSV/JSON → DB."""

import asyncio


async def seed():
    """Seed the database with initial data for development."""
    print("Seeding database...")
    # TODO: Add seed data for restaurants, branches, users, SLA configs
    print("Seeding complete.")


if __name__ == "__main__":
    asyncio.run(seed())
