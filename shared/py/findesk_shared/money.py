"""Money conventions: integer paise everywhere; INR formatting at the edge."""

from __future__ import annotations

from decimal import Decimal


def paise_to_rupees(amount_paise: int) -> Decimal:
    return Decimal(amount_paise) / Decimal(100)


def format_inr(amount_paise: int, *, symbol: bool = True) -> str:
    """Indian digit grouping: ₹12,34,567.89 (lakh/crore), paise always 2dp."""
    negative = amount_paise < 0
    rupees, paise = divmod(abs(amount_paise), 100)
    digits = str(rupees)
    if len(digits) > 3:
        head, tail = digits[:-3], digits[-3:]
        groups = []
        while len(head) > 2:
            groups.insert(0, head[-2:])
            head = head[:-2]
        if head:
            groups.insert(0, head)
        grouped = ",".join([*groups, tail])
    else:
        grouped = digits
    out = f"{grouped}.{paise:02d}"
    if symbol:
        out = f"₹{out}"
    return f"-{out}" if negative else out
