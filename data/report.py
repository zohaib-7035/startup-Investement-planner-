import html

# Op 1 — fallback constant (str, not dict — unique in this codebase; return directly, no .copy())
_EMPTY_REPORT = (
    "<!DOCTYPE html><html lang=\"en\"><head><meta charset=\"UTF-8\">"
    "<title>Stock Report</title>"
    "<style>body{font-family:Arial,sans-serif;max-width:860px;margin:40px auto;"
    "padding:20px;color:#333;}</style></head>"
    "<body><h1>Stock Report</h1><p>No data available.</p></body></html>"
)

# Op 4 — badge colour map
_BADGE_COLOURS = {
    "BUY": "#28a745",
    "SELL": "#dc3545",
    "HOLD": "#fd7e14",
}
_BADGE_COLOUR_DEFAULT = "#6c757d"


# Op 2
def _safe_field(value):
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.2f}"
    return html.escape(str(value))


# Op 3
def _format_confidence(score):
    if score is None:
        return "N/A"
    try:
        v = float(score)
    except (TypeError, ValueError):
        return "N/A"
    v = max(0.0, min(1.0, v))
    return f"{int(round(v * 100))}%"


# Op 4
def _badge_colour(recommendation):
    return _BADGE_COLOURS.get(str(recommendation).upper(), _BADGE_COLOUR_DEFAULT)


# Op 5
def _render_allocation(alloc):
    if not alloc or not isinstance(alloc, dict):
        return "N/A"
    items = "".join(
        f"<li>{html.escape(str(ticker))}: {float(weight) * 100:.1f}%</li>"
        for ticker, weight in alloc.items()
    )
    return f"<ul>{items}</ul>"


# Op 6
def _render_dict_section(d):
    if not isinstance(d, dict) or not d:
        return "N/A"
    items = "".join(
        f"<dt>{html.escape(str(k))}</dt><dd>{_safe_field(v)}</dd>"
        for k, v in d.items()
    )
    return f"<dl>{items}</dl>"


# Op 7
def render_report(data):
    """Return a self-contained HTML report string from pipeline outputs. Returns str, never raises."""
    if not data or not isinstance(data, dict):
        return _EMPTY_REPORT
    try:
        company = _safe_field(data.get("company_name"))
        recommendation = _safe_field(data.get("recommendation"))
        badge_bg = _badge_colour(data.get("recommendation"))
        confidence = _format_confidence(data.get("confidence_score"))
        technical = _render_dict_section(data.get("technical_signals"))
        fundamentals = _render_dict_section(data.get("fundamentals"))
        sentiment = _safe_field(data.get("sentiment"))
        risk_level = _safe_field(data.get("risk_level"))
        allocation = _render_allocation(data.get("portfolio_allocation"))
        timestamp = _safe_field(data.get("timestamp"))

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Stock Report — {company}</title>
<style>
  body {{
    font-family: Arial, sans-serif;
    max-width: 860px;
    margin: 40px auto;
    padding: 20px;
    color: #333;
    background: #f8f9fa;
  }}
  h1 {{ margin-bottom: 4px; word-break: break-word; }}
  .timestamp {{ color: #888; font-size: 0.85em; margin-bottom: 24px; }}
  .card {{
    background: #fff;
    border: 1px solid #dee2e6;
    border-radius: 6px;
    padding: 16px 20px;
    margin-bottom: 16px;
  }}
  .card h2 {{
    margin: 0 0 10px;
    font-size: 1em;
    text-transform: uppercase;
    color: #555;
    letter-spacing: 0.05em;
  }}
  .badge {{
    display: inline-block;
    padding: 6px 18px;
    border-radius: 4px;
    color: #fff;
    font-weight: bold;
    font-size: 1.1em;
    background: {badge_bg};
  }}
  dl {{ margin: 0; }}
  dt {{ font-weight: bold; float: left; clear: left; width: 160px; }}
  dd {{ margin-left: 170px; margin-bottom: 4px; }}
  ul {{ margin: 0; padding-left: 20px; }}
  li {{ margin-bottom: 4px; }}
</style>
</head>
<body>
  <h1>{company}</h1>
  <div class="timestamp">Generated: {timestamp}</div>

  <div class="card">
    <h2>Recommendation</h2>
    <span class="badge">{recommendation}</span>
  </div>

  <div class="card">
    <h2>Confidence Score</h2>
    <p>{confidence}</p>
  </div>

  <div class="card">
    <h2>Technical Signals</h2>
    {technical}
  </div>

  <div class="card">
    <h2>Fundamentals</h2>
    {fundamentals}
  </div>

  <div class="card">
    <h2>Sentiment</h2>
    <p>{sentiment}</p>
  </div>

  <div class="card">
    <h2>Risk Level</h2>
    <p>{risk_level}</p>
  </div>

  <div class="card">
    <h2>Portfolio Allocation</h2>
    {allocation}
  </div>
</body>
</html>"""
    except Exception:
        return _EMPTY_REPORT
