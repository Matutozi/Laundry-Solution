from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer


async def create_customer(name: str, phone: str, tier: int, db: AsyncSession) -> Customer:
    """Raises ValueError on duplicate phone."""
    existing = await db.execute(select(Customer).where(Customer.phone == phone))
    if existing.scalar_one_or_none():
        raise ValueError(f"Phone '{phone}' is already registered")
    customer = Customer(name=name, phone=phone, tier=tier)
    db.add(customer)
    await db.flush()
    return customer


async def search_customers(q: str, db: AsyncSession) -> list[Customer]:
    result = await db.execute(
        select(Customer)
        .where(or_(Customer.phone == q, Customer.name.ilike(f"%{q}%")))
        .limit(20)
    )
    return list(result.scalars().all())
