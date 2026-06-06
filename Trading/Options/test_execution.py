"""Correctness guards for the realistic fill model (src/utils/execution.py)."""
from src.utils.execution import net_open, net_close


def test_fraction_spans_mid_to_natural_and_hurts_both_ways():
    # A debit calendar-like spread: short cheap near leg, long richer far leg.
    legs = [(1.00, 1.10, False), (2.00, 2.20, True)]  # (bid, ask, is_long)
    near_mid, far_mid = 1.05, 2.10

    # fraction=0 -> mid on every leg.
    assert net_open(legs, 0.0) == far_mid - near_mid
    assert net_close(legs, 0.0) == far_mid - near_mid

    # fraction=1 -> natural price: open = far_ask - near_bid; close = far_bid - near_ask.
    assert net_open(legs, 1.0) == 2.20 - 1.00
    assert net_close(legs, 1.0) == 2.00 - 1.10

    # A wider fill fraction always costs more to open and yields less to close.
    assert net_open(legs, 1.0) > net_open(legs, 0.5) > net_open(legs, 0.0)
    assert net_close(legs, 1.0) < net_close(legs, 0.5) < net_close(legs, 0.0)


def test_credit_spread_pnl_is_signed_correctly():
    # Bull put credit spread: short the richer high-strike put, long the cheaper low-strike put.
    legs = [(1.50, 1.60, False), (0.40, 0.50, True)]
    assert net_open(legs, 0.5) < 0                      # net credit received (entry_price < 0)

    # If it expires worthless, closing costs ~0 -> P&L = close - open > 0 (a win, not a loss).
    worthless = [(0.0, 0.01, False), (0.0, 0.01, True)]
    pnl = net_close(worthless, 0.5) - net_open(legs, 0.5)
    assert pnl > 0


def test_extra_slippage_is_an_additional_haircut():
    legs = [(1.00, 1.10, False), (2.00, 2.20, True)]
    assert net_open(legs, 0.5, extra=0.01) > net_open(legs, 0.5, extra=0.0)
    assert net_close(legs, 0.5, extra=0.01) < net_close(legs, 0.5, extra=0.0)
