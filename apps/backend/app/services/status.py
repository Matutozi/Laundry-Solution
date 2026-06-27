"""Status-transition service.

validate_transition is a pure function — no I/O, fully unit-testable.
apply_status_transition is the async DB layer that calls it.
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.order import Order, OrderStatus
from app.models.status_event import StatusEvent

# Forward-only pipeline.  Terminal states map to empty sets.
VALID_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.received:   {OrderStatus.processing},
    OrderStatus.processing: {OrderStatus.ready},
    OrderStatus.ready:      {OrderStatus.picked_up, OrderStatus.delivered},
    OrderStatus.picked_up:  set(),
    OrderStatus.delivered:  set(),
    OrderStatus.cancelled:  set(),
}


class InvalidTransitionError(ValueError):
    def __init__(self, from_status: OrderStatus, to_status: OrderStatus) -> None:
        allowed = VALID_TRANSITIONS.get(from_status, set())
        hint = ", ".join(s.value for s in allowed) if allowed else "none — terminal state"
        super().__init__(
            f"Cannot move order from '{from_status.value}' to '{to_status.value}'. "
            f"Allowed next states: {hint}"
        )
        self.from_status = from_status
        self.to_status = to_status


def validate_transition(from_status: OrderStatus, to_status: OrderStatus) -> None:
    """Pure. Raises InvalidTransitionError if the move is not permitted."""
    if to_status not in VALID_TRANSITIONS.get(from_status, set()):
        raise InvalidTransitionError(from_status, to_status)


async def apply_status_transition(
    order_id: str,
    to_status: OrderStatus,
    staff_id: str,
    db: AsyncSession,
) -> tuple[Order, StatusEvent]:
    """
    Validate and apply a forward status move.

    Bumps order.version on every accepted change so clients can detect conflicts.
    Raises ValueError if the order is not found.
    Raises InvalidTransitionError if the move is not permitted.
    """
    order = await db.get(Order, order_id)
    if order is None:
        raise ValueError(f"Order '{order_id}' not found")

    validate_transition(order.status, to_status)

    from_status = order.status
    order.status = to_status
    order.version += 1

    event = StatusEvent(
        order_id=order.id,
        staff_id=staff_id,
        from_status=from_status,
        to_status=to_status,
    )
    db.add(event)
    await db.flush()
    return order, event
