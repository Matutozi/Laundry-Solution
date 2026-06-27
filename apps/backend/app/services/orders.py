"""
Order creation service.

The public entry point is `create_order`. It:
  1. Loads the customer to get their tier.
  2. Loads PriceRule rows for the requested services and tier.
  3. Calls price_order() — the pure pricing engine — to compute the total.
  4. Persists Order + OrderLine rows with the server-computed amounts.

The server always recomputes. Clients never send prices.
"""

from __future__ import annotations

import secrets
import string

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.customer import Customer
from app.models.order import Order, OrderStatus, Turnaround
from app.models.order_line import OrderLine
from app.models.price_rule import PriceRule
from app.services.pricing import OrderLineInput, OrderPricing, PriceRuleNotFound, price_order


def generate_pickup_code() -> str:
    """8-char uppercase alphanumeric code, cryptographically random."""
    alphabet = string.ascii_uppercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(8))


async def load_price_rules(
    service_ids: list[str],
    tier: int,
    db: AsyncSession,
) -> dict[tuple[str, int], int]:
    """Fetch PriceRule rows and return them as the dict expected by price_order()."""
    result = await db.execute(
        select(PriceRule).where(
            PriceRule.service_id.in_(service_ids),
            PriceRule.tier == tier,
        )
    )
    return {(r.service_id, r.tier): r.price_kobo for r in result.scalars().all()}


async def create_order(
    branch_id: str,
    attendant_id: str,
    customer_id: str,
    turnaround: Turnaround,
    line_inputs: list[OrderLineInput],
    db: AsyncSession,
) -> tuple[Order, OrderPricing]:
    """
    Create and persist a new order with server-computed pricing.

    Raises:
        ValueError:         Customer not found.
        PriceRuleNotFound:  A service has no PriceRule for the customer's tier.
    """
    customer = await db.get(Customer, customer_id)
    if customer is None:
        raise ValueError(f"Customer '{customer_id}' not found")

    service_ids = [li.service_id for li in line_inputs]
    rules = await load_price_rules(service_ids, customer.tier, db)

    # Raises PriceRuleNotFound if any service is missing a rule — deliberately uncaught here.
    pricing = price_order(customer.tier, line_inputs, turnaround, rules)

    pickup_code = generate_pickup_code()

    order = Order(
        branch_id=branch_id,
        attendant_id=attendant_id,
        customer_id=customer_id,
        turnaround=turnaround,
        total_kobo=pricing.total_kobo,
        pickup_code=pickup_code,
        status=OrderStatus.received,
        version=1,
    )
    db.add(order)
    await db.flush()  # obtain order.id before inserting lines

    for priced in pricing.lines:
        db.add(OrderLine(
            order_id=order.id,
            service_id=priced.service_id,
            piece_count=priced.piece_count,
            unit_price_kobo=priced.unit_price_kobo,
            line_total_kobo=priced.line_total_kobo,
        ))

    await db.flush()
    return order, pricing
