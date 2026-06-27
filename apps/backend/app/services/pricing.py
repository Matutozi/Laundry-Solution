"""
Pricing engine — pure functions, zero I/O, zero floats.

All amounts are integer kobo throughout. Turnaround multipliers are stored as
(numerator, denominator) rational pairs so that express (1.5×) is computed as
ceiling(kobo × 3 / 2) using only integer arithmetic. Rounding is applied once
per line (not per unit, not at the total), then lines are summed.
"""

from __future__ import annotations

from dataclasses import dataclass

# Turnaround is defined on the Order model (it is a DB column enum).
# Re-exported here so callers that only touch the pricing layer don't need
# to import from models directly.
from app.models.order import Turnaround

__all__ = ["Turnaround", "PriceRuleNotFound", "OrderLineInput", "PricedLine", "OrderPricing", "price_order"]

# Rational multipliers — (numerator, denominator). Never floats.
_MULTIPLIER: dict[Turnaround, tuple[int, int]] = {
    Turnaround.regular:  (1, 1),
    Turnaround.express:  (3, 2),
    Turnaround.same_day: (3, 1),
}


class PriceRuleNotFound(Exception):
    """Raised when no PriceRule row exists for a (service_id, tier) combination."""

    def __init__(self, service_id: str, tier: int) -> None:
        super().__init__(
            f"No price rule for service '{service_id}' at tier {tier}. "
            "Add a PriceRule row before creating orders for this service."
        )
        self.service_id = service_id
        self.tier = tier


@dataclass(frozen=True)
class OrderLineInput:
    service_id: str
    piece_count: int


@dataclass(frozen=True)
class PricedLine:
    service_id: str
    piece_count: int
    unit_price_kobo: int   # price per piece before turnaround
    line_total_kobo: int   # after multiplier, after rounding


@dataclass(frozen=True)
class OrderPricing:
    lines: tuple[PricedLine, ...]
    total_kobo: int
    turnaround: Turnaround


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _ceiling_multiply(kobo: int, num: int, den: int) -> int:
    """Return ceil(kobo × num / den) using integer arithmetic only."""
    return (kobo * num + den - 1) // den


def _price_line(unit_price_kobo: int, piece_count: int, turnaround: Turnaround) -> int:
    """
    Compute one line total in kobo.

    Rounding is applied at the line level (not per-piece, not at the order total)
    so each line's displayed price matches what is stored.
    """
    num, den = _MULTIPLIER[turnaround]
    return _ceiling_multiply(unit_price_kobo * piece_count, num, den)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def price_order(
    tier: int,
    lines: list[OrderLineInput],
    turnaround: Turnaround,
    price_rules: dict[tuple[str, int], int],
) -> OrderPricing:
    """
    Compute the full pricing breakdown for an order.

    Args:
        tier:         Customer tier (1–3).
        lines:        Ordered list of (service_id, piece_count) inputs.
        turnaround:   Delivery speed — determines the multiplier.
        price_rules:  Pre-loaded lookup mapping (service_id, tier) → unit price in kobo.
                      Build this from PriceRule rows before calling.

    Returns:
        OrderPricing with a per-line breakdown and an integer kobo total.

    Raises:
        PriceRuleNotFound: If any line's service has no rule for the given tier.
        ValueError:        If any piece_count is less than 1.
    """
    if not lines:
        return OrderPricing(lines=(), total_kobo=0, turnaround=turnaround)

    priced: list[PricedLine] = []
    for line in lines:
        if line.piece_count < 1:
            raise ValueError(
                f"piece_count must be >= 1, got {line.piece_count} for service '{line.service_id}'"
            )

        key = (line.service_id, tier)
        if key not in price_rules:
            raise PriceRuleNotFound(line.service_id, tier)

        unit_price = price_rules[key]
        line_total = _price_line(unit_price, line.piece_count, turnaround)
        priced.append(
            PricedLine(
                service_id=line.service_id,
                piece_count=line.piece_count,
                unit_price_kobo=unit_price,
                line_total_kobo=line_total,
            )
        )

    total = sum(p.line_total_kobo for p in priced)
    return OrderPricing(lines=tuple(priced), total_kobo=total, turnaround=turnaround)
