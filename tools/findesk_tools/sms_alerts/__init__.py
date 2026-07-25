"""Bank debit-alert SMS parsing (LeakRadar source #2).

PS1 names SMS and email as transaction sources. This parses the alert *formats*
from recorded samples into the same shape the CSV statement parser emits, so
everything downstream (categorization, cadence, drift) is identical regardless of
where a debit came from.

Fixture-driven on purpose: FinDesk has no carrier or inbox access, and the README
integration table says "Fixture-tested", not "Live".
"""

from findesk_tools.sms_alerts.parser import ParsedSms, parse_alert, parse_inbox

__all__ = ["ParsedSms", "parse_alert", "parse_inbox"]
