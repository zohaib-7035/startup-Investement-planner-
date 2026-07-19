"""
Market context module — stub for VC Brain v1.
Preserves the public surface of the original macro_data.py.
Full market-sizing integration is deferred (out of scope v1).
"""


def get_macro_indicators() -> dict:
    """Return macroeconomic indicators. Stub returns empty dict in VC Brain v1."""
    return {}


def get_yield_curve() -> dict:
    """Return yield curve data. Stub returns empty dict in VC Brain v1."""
    return {}


def get_yield_curve_signal() -> dict:
    """Return yield curve signal. Stub returns neutral signal in VC Brain v1."""
    return {"signal": "UNKNOWN", "spread": None}
