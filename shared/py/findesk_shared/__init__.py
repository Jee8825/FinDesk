"""FinDesk shared utilities — hand-written, cross-layer conventions.

Generated contract models live in the sibling ``findesk_contracts`` package;
never hand-edit those.
"""

from findesk_shared.ids import uuid7
from findesk_shared.memory_keys import vendor_scope, vendor_slug
from findesk_shared.money import format_inr, paise_to_rupees

__all__ = ["uuid7", "format_inr", "paise_to_rupees", "vendor_scope", "vendor_slug"]
