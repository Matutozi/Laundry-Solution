"""Admin-only endpoints: dashboard metrics and pricing rule CRUD."""

from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.dependencies.auth import require_role
from app.models.order import Order
from app.models.payment import Payment
from app.models.price_rule import PriceRule
from app.models.service import Service
from app.models.staff import Staff, StaffRole

router = APIRouter(prefix="/admin", tags=["admin"])

_MANAGER_ADMIN = require_role(StaffRole.manager, StaffRole.admin)


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/dashboard")
async def dashboard(
    branch_id: Optional[str] = Query(None),
    from_date: Optional[date] = Query(None),
    to_date: Optional[date] = Query(None),
    _staff: Staff = Depends(_MANAGER_ADMIN),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Aggregate metrics: revenue received, order volume, outstanding balance."""
    q = select(Order)
    if branch_id:
        q = q.where(Order.branch_id == branch_id)
    if from_date:
        q = q.where(Order.created_at >= datetime.combine(from_date, datetime.min.time()))
    if to_date:
        q = q.where(Order.created_at <= datetime.combine(to_date, datetime.max.time()))

    orders = (await db.execute(q)).scalars().all()
    order_ids = [o.id for o in orders]
    total_billed: int = sum(o.total_kobo for o in orders)

    revenue_kobo: int = 0
    if order_ids:
        result = await db.execute(
            select(func.coalesce(func.sum(Payment.amount_kobo), 0))
            .where(Payment.order_id.in_(order_ids))
        )
        revenue_kobo = int(result.scalar() or 0)

    return {
        "revenue_kobo": revenue_kobo,
        "order_count": len(orders),
        "outstanding_kobo": total_billed - revenue_kobo,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Pricing rules
# ─────────────────────────────────────────────────────────────────────────────


@router.get("/pricing")
async def get_pricing(
    _staff: Staff = Depends(_MANAGER_ADMIN),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Return all services and their price rules for the matrix editor."""
    services = (await db.execute(select(Service).order_by(Service.name))).scalars().all()
    rules = (await db.execute(select(PriceRule))).scalars().all()
    return {
        "services": [{"id": s.id, "name": s.name} for s in services],
        "rules": [
            {"service_id": r.service_id, "tier": r.tier, "price_kobo": r.price_kobo}
            for r in rules
        ],
    }


class PriceRuleUpdate(BaseModel):
    price_kobo: int


@router.put("/pricing/{service_id}/rules/{tier}")
async def update_price_rule(
    service_id: str,
    tier: int,
    body: PriceRuleUpdate,
    _staff: Staff = Depends(_MANAGER_ADMIN),
    db: AsyncSession = Depends(get_session),
) -> dict:
    """Upsert a single price rule (service × tier → kobo)."""
    if tier < 1 or tier > 3:
        raise HTTPException(status_code=422, detail="tier must be 1, 2, or 3")
    if body.price_kobo < 0:
        raise HTTPException(status_code=422, detail="price_kobo must be ≥ 0")

    existing = (await db.execute(
        select(PriceRule).where(
            PriceRule.service_id == service_id,
            PriceRule.tier == tier,
        )
    )).scalar_one_or_none()

    if existing:
        existing.price_kobo = body.price_kobo
    else:
        db.add(PriceRule(service_id=service_id, tier=tier, price_kobo=body.price_kobo))

    await db.flush()
    return {"service_id": service_id, "tier": tier, "price_kobo": body.price_kobo}
