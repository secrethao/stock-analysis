import pandas as pd


def summarize_dividend_frame(frame) -> tuple[float | None, float | None]:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return None, None
    if "现金分红-现金分红比例" not in frame.columns or "报告期" not in frame.columns:
        return None, None
    by_year: dict[int, float] = {}
    for _, row in frame.iterrows():
        progress = str(row.get("方案进度") or "")
        if "实施" not in progress:
            continue
        cash = _num(row.get("现金分红-现金分红比例"))
        year = _year(row.get("报告期"))
        if cash is None or cash <= 0 or year is None:
            continue
        by_year[year] = by_year.get(year, 0.0) + cash / 10
    if not by_year:
        return None, None
    latest_year = max(by_year)
    dps = by_year[latest_year]
    cagr = None
    old_year = latest_year - 3
    if old_year in by_year and by_year[old_year] > 0 and dps > 0:
        cagr = (dps / by_year[old_year]) ** (1 / 3) - 1
    return dps, cagr


def _year(value) -> int | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if hasattr(value, "year"):
        return int(value.year)
    text = str(value)
    if len(text) < 4 or not text[:4].isdigit():
        return None
    return int(text[:4])


def _num(value) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
    except TypeError:
        if value is None:
            return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
