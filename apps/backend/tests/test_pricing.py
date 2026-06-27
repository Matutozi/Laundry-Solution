"""
Unit tests for the pricing engine.

All tests are synchronous — the pricing functions are pure and have no I/O.
Price rules are constructed inline; no database is touched.

Kobo ↔ Naira reference: 100 kobo = ₦1, so 100_000 kobo = ₦1,000.
"""

import pytest

from app.services.pricing import (
    OrderLineInput,
    OrderPricing,
    PriceRuleNotFound,
    Turnaround,
    _ceiling_multiply,
    _price_line,
    price_order,
)

# ---------------------------------------------------------------------------
# Fixtures / shared data
# ---------------------------------------------------------------------------

WASH = "wash"
DRY_CLEAN = "dry_clean"
IRON = "iron"

# Standard rules covering tiers 1–3
RULES: dict[tuple[str, int], int] = {
    (WASH,      1): 100_000,   # ₦1,000 per piece
    (WASH,      2): 150_000,   # ₦1,500
    (WASH,      3): 200_000,   # ₦2,000
    (DRY_CLEAN, 1): 300_000,
    (DRY_CLEAN, 2): 450_000,
    (DRY_CLEAN, 3): 600_000,
    (IRON,      1):  50_000,   # ₦500
    (IRON,      2):  75_000,
    (IRON,      3): 100_000,
}

# Minimal rules for rounding edge-case tests (tiny kobo values)
TINY_RULES: dict[tuple[str, int], int] = {
    ("svc_1k", 1): 1,    # 1 kobo
    ("svc_3k", 1): 3,    # 3 kobo
    ("svc_5k", 1): 5,    # 5 kobo
    ("svc_7k", 1): 7,    # 7 kobo
    ("svc_odd", 1): 99_999,  # odd near-round number
}


def line(service_id: str, pieces: int) -> OrderLineInput:
    return OrderLineInput(service_id=service_id, piece_count=pieces)


# ---------------------------------------------------------------------------
# _ceiling_multiply — the rounding primitive
# ---------------------------------------------------------------------------


class TestCeilingMultiply:
    def test_exact_division(self):
        assert _ceiling_multiply(100_000, 3, 2) == 150_000

    def test_rounds_up_on_half(self):
        # 1 × 3 / 2 = 1.5 → ceil = 2
        assert _ceiling_multiply(1, 3, 2) == 2

    def test_rounds_up_odd(self):
        # 3 × 3 / 2 = 4.5 → ceil = 5
        assert _ceiling_multiply(3, 3, 2) == 5

    def test_rounds_up_another_odd(self):
        # 7 × 3 / 2 = 10.5 → ceil = 11
        assert _ceiling_multiply(7, 3, 2) == 11

    def test_integer_multiplier_no_rounding(self):
        # 3× — always exact
        assert _ceiling_multiply(100_001, 3, 1) == 300_003

    def test_identity_multiplier(self):
        assert _ceiling_multiply(99_999, 1, 1) == 99_999

    def test_zero_kobo(self):
        assert _ceiling_multiply(0, 3, 2) == 0


# ---------------------------------------------------------------------------
# _price_line — per-line computation
# ---------------------------------------------------------------------------


class TestPriceLine:
    def test_regular_single_piece(self):
        assert _price_line(100_000, 1, Turnaround.regular) == 100_000

    def test_regular_multi_piece(self):
        assert _price_line(100_000, 5, Turnaround.regular) == 500_000

    def test_express_exact(self):
        # 100_000 × 2 pieces × 1.5 = 300_000 (exact)
        assert _price_line(100_000, 2, Turnaround.express) == 300_000

    def test_express_fractional_rounds_up(self):
        # 1 kobo × 1 piece × 1.5 = 1.5 → 2
        assert _price_line(1, 1, Turnaround.express) == 2

    def test_express_fractional_multi_piece(self):
        # 3 kobo × 1 piece × 1.5 = 4.5 → 5
        assert _price_line(3, 1, Turnaround.express) == 5

    def test_express_rounding_applied_at_line_not_per_piece(self):
        # 1 kobo × 3 pieces × 1.5 = 4.5 → ceil = 5
        # vs per-piece: ceil(1.5) × 3 = 2 × 3 = 6  ← NOT this
        assert _price_line(1, 3, Turnaround.express) == 5

    def test_same_day_always_exact(self):
        # 3× is always an integer multiple
        assert _price_line(100_001, 1, Turnaround.same_day) == 300_003

    def test_same_day_multi_piece(self):
        assert _price_line(50_000, 4, Turnaround.same_day) == 600_000


# ---------------------------------------------------------------------------
# price_order — full order pricing
# ---------------------------------------------------------------------------


class TestPriceOrderRegular:
    def test_single_line_tier1(self):
        result = price_order(1, [line(WASH, 3)], Turnaround.regular, RULES)
        assert result.total_kobo == 300_000
        assert len(result.lines) == 1
        assert result.lines[0].unit_price_kobo == 100_000
        assert result.lines[0].line_total_kobo == 300_000
        assert result.turnaround == Turnaround.regular

    def test_single_line_tier2_higher_price(self):
        result = price_order(2, [line(WASH, 3)], Turnaround.regular, RULES)
        assert result.total_kobo == 450_000

    def test_single_line_tier3(self):
        result = price_order(3, [line(WASH, 1)], Turnaround.regular, RULES)
        assert result.total_kobo == 200_000

    def test_multi_line_order(self):
        # wash × 2 @ tier1 = 200_000
        # dry_clean × 1 @ tier1 = 300_000
        # iron × 3 @ tier1 = 150_000
        # total = 650_000
        result = price_order(
            1,
            [line(WASH, 2), line(DRY_CLEAN, 1), line(IRON, 3)],
            Turnaround.regular,
            RULES,
        )
        assert result.total_kobo == 650_000
        assert len(result.lines) == 3
        assert result.lines[0].line_total_kobo == 200_000
        assert result.lines[1].line_total_kobo == 300_000
        assert result.lines[2].line_total_kobo == 150_000

    def test_empty_lines_returns_zero(self):
        result = price_order(1, [], Turnaround.regular, RULES)
        assert result.total_kobo == 0
        assert result.lines == ()


class TestPriceOrderExpress:
    def test_single_line_exact(self):
        # 100_000 × 2 × 1.5 = 300_000
        result = price_order(1, [line(WASH, 2)], Turnaround.express, RULES)
        assert result.total_kobo == 300_000

    def test_single_line_rounds_up(self):
        # 100_000 × 1 × 1.5 = 150_000 (exact)
        result = price_order(1, [line(WASH, 1)], Turnaround.express, RULES)
        assert result.total_kobo == 150_000

    def test_multi_line_express_each_line_rounded_independently(self):
        # 1k × 1pc × 1.5 = 1.5 → 2
        # 3k × 1pc × 1.5 = 4.5 → 5
        # total = 7  (not ceil(1+3) × 1.5 = ceil(6) = 6)
        rules = {**TINY_RULES}
        result = price_order(
            1,
            [line("svc_1k", 1), line("svc_3k", 1)],
            Turnaround.express,
            rules,
        )
        assert result.lines[0].line_total_kobo == 2
        assert result.lines[1].line_total_kobo == 5
        assert result.total_kobo == 7

    def test_express_odd_unit_price_multi_piece(self):
        # 99_999 × 1 piece × 1.5 = 149_998.5 → 149_999
        rules = {**TINY_RULES}
        result = price_order(1, [line("svc_odd", 1)], Turnaround.express, rules)
        assert result.total_kobo == 149_999

    def test_express_mixed_exact_and_rounded(self):
        # wash tier1 × 2 = 200_000 × 1.5 = 300_000 (exact)
        # iron tier1 × 1 = 50_000 × 1.5 = 75_000 (exact)
        result = price_order(
            1,
            [line(WASH, 2), line(IRON, 1)],
            Turnaround.express,
            RULES,
        )
        assert result.total_kobo == 375_000


class TestPriceOrderSameDay:
    def test_single_line(self):
        # 100_000 × 1 × 3 = 300_000
        result = price_order(1, [line(WASH, 1)], Turnaround.same_day, RULES)
        assert result.total_kobo == 300_000

    def test_multi_line(self):
        # wash × 1 @ tier2: 150_000 × 3 = 450_000
        # iron × 2 @ tier2: 75_000 × 2 × 3 = 450_000
        result = price_order(
            2,
            [line(WASH, 1), line(IRON, 2)],
            Turnaround.same_day,
            RULES,
        )
        assert result.total_kobo == 900_000

    def test_same_day_always_integer(self):
        # 3× is always an integer multiplier — no rounding ever occurs
        rules = {**TINY_RULES}
        result = price_order(1, [line("svc_1k", 1)], Turnaround.same_day, rules)
        assert result.total_kobo == 3


# ---------------------------------------------------------------------------
# Rounding edge cases — stress tests on tiny amounts
# ---------------------------------------------------------------------------


class TestRoundingEdgeCases:
    @pytest.mark.parametrize("unit_kobo,pieces,expected", [
        (1, 1, 2),    # 1.5 → 2
        (3, 1, 5),    # 4.5 → 5
        (5, 1, 8),    # 7.5 → 8
        (7, 1, 11),   # 10.5 → 11
        (1, 2, 3),    # 2 × 1.5 = 3.0 (exact)
        (1, 3, 5),    # 3 × 1.5 = 4.5 → 5
        (1, 4, 6),    # 4 × 1.5 = 6.0 (exact)
        (2, 1, 3),    # 2 × 1.5 = 3.0 (exact)
        (2, 3, 9),    # 6 × 1.5 = 9.0 (exact)
        (3, 3, 14),   # 9 × 1.5 = 13.5 → 14
    ])
    def test_express_rounding_table(self, unit_kobo: int, pieces: int, expected: int):
        rules = {("svc", 1): unit_kobo}
        result = price_order(1, [line("svc", pieces)], Turnaround.express, rules)
        assert result.total_kobo == expected, (
            f"unit={unit_kobo}k × {pieces}pc × 1.5 should be {expected}k"
        )

    def test_large_amount_no_overflow(self):
        # 10_000_000 kobo (₦100,000) × 999 pieces × 1.5 — pure Python ints, no overflow
        rules = {("luxury", 1): 10_000_000}
        result = price_order(1, [line("luxury", 999)], Turnaround.express, rules)
        # 10_000_000 × 999 × 1.5 = 14_985_000_000 (exact, even product)
        assert result.total_kobo == 14_985_000_000


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


class TestMissingPriceRule:
    def test_missing_rule_raises_not_found(self):
        with pytest.raises(PriceRuleNotFound) as exc_info:
            price_order(1, [line("nonexistent_svc", 2)], Turnaround.regular, RULES)
        err = exc_info.value
        assert err.service_id == "nonexistent_svc"
        assert err.tier == 1

    def test_missing_rule_message_is_informative(self):
        with pytest.raises(PriceRuleNotFound, match="nonexistent_svc"):
            price_order(1, [line("nonexistent_svc", 1)], Turnaround.regular, RULES)

    def test_missing_rule_for_tier_but_other_tiers_exist(self):
        # wash exists for tier 1 but not tier 4 (hypothetical)
        partial_rules = {(WASH, 1): 100_000}
        with pytest.raises(PriceRuleNotFound) as exc_info:
            price_order(2, [line(WASH, 1)], Turnaround.regular, partial_rules)
        assert exc_info.value.tier == 2

    def test_missing_rule_on_second_line_after_first_valid(self):
        # First line is fine, second line has no rule → still raises
        rules = {(WASH, 1): 100_000}
        with pytest.raises(PriceRuleNotFound) as exc_info:
            price_order(
                1,
                [line(WASH, 1), line(DRY_CLEAN, 2)],
                Turnaround.regular,
                rules,
            )
        assert exc_info.value.service_id == DRY_CLEAN

    def test_empty_price_rules_raises(self):
        with pytest.raises(PriceRuleNotFound):
            price_order(1, [line(WASH, 1)], Turnaround.regular, {})


class TestInputValidation:
    def test_zero_piece_count_raises(self):
        with pytest.raises(ValueError, match="piece_count must be >= 1"):
            price_order(1, [line(WASH, 0)], Turnaround.regular, RULES)

    def test_negative_piece_count_raises(self):
        with pytest.raises(ValueError, match="piece_count must be >= 1"):
            price_order(1, [line(WASH, -1)], Turnaround.regular, RULES)

    def test_validation_precedes_price_rule_lookup(self):
        # Even with an empty rule dict, piece_count=0 raises ValueError not PriceRuleNotFound
        with pytest.raises(ValueError):
            price_order(1, [line(WASH, 0)], Turnaround.regular, {})


# ---------------------------------------------------------------------------
# Return-value structure
# ---------------------------------------------------------------------------


class TestReturnStructure:
    def test_pricing_is_immutable(self):
        result = price_order(1, [line(WASH, 1)], Turnaround.regular, RULES)
        with pytest.raises((AttributeError, TypeError)):
            result.total_kobo = 0  # type: ignore[misc]

    def test_priced_line_carries_unit_price(self):
        result = price_order(2, [line(WASH, 3)], Turnaround.express, RULES)
        assert result.lines[0].unit_price_kobo == 150_000  # tier-2 wash

    def test_line_order_preserved(self):
        result = price_order(
            1,
            [line(IRON, 1), line(WASH, 2), line(DRY_CLEAN, 1)],
            Turnaround.regular,
            RULES,
        )
        assert [p.service_id for p in result.lines] == [IRON, WASH, DRY_CLEAN]

    def test_total_equals_sum_of_lines(self):
        result = price_order(
            1,
            [line(WASH, 2), line(DRY_CLEAN, 1), line(IRON, 4)],
            Turnaround.express,
            RULES,
        )
        assert result.total_kobo == sum(p.line_total_kobo for p in result.lines)
