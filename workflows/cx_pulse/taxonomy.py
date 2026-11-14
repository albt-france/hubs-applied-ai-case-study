"""Themes and severity levels for CX Pulse. Shared by the prompt, the rules, the test set and the docs.

One primary theme per review: if a review mixes praise and a complaint, the complaint wins
(the brand wants to know what to fix). Severity says how urgently someone should act.
"""

THEMES = {
    "not_received": "The customer says the order has not arrived (yet), whatever the due date.",
    "delivery_late": "The order arrived late, or the customer complains about slow or long delivery times.",
    "wrong_or_incomplete": "Wrong item, different model, or part of the order missing.",
    "damaged_defective": "Item arrived broken, scratched, used-looking or does not work.",
    "quality_mismatch": "Item works but quality is poor or it differs from the photo/description (colour, size, material).",
    "seller_service": "Cancellation, refund, return/exchange process, invoice, or the seller not answering.",
    "other": "A complaint that fits none of the above (pick-up at the post office, shipping price, vague 'did not deliver what was promised').",
    "praise": "No complaint: positive or neutral feedback only.",
}

SEVERITY = {
    "high": "The customer did not get what they paid for, lost money, or the order was cancelled. Act within 24h.",
    "medium": "The customer got the product but with a clear problem (late, poor quality, minor defect kept).",
    "low": "A small remark inside an otherwise positive review.",
    "none": "No problem reported.",
}

NEGATIVE_THEMES = [t for t in THEMES if t != "praise"]
