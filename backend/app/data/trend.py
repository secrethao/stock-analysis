import re
from datetime import date, datetime

import pandas as pd

from app.data.cache import get_blob_cached, set_blob_cached
from app.data.fetcher import QuoteError, _secucode

PERIOD_NAMES = {
    (3, 31): "一季报",
    (6, 30): "半年报",
    (9, 30): "三季报",
    (12, 31): "年报",
}
LOOKBACK_YEARS = 5


def get_trend(code: str) -> dict:
    normalized = code.strip()
    if not re.fullmatch(r"\d{6}", normalized):
        raise QuoteError("请输入 6 位 A 股代码")
    cached = get_blob_cached(f"trend:{normalized}")
    if cached is not None:
        return cached
    payload = _fetch_trend(normalized)
    if payload["points"]:
        set_blob_cached(f"trend:{normalized}", payload)
    return payload


def build_trend(financial_rows: list[dict], cap_rows: list[dict], today: date | None = None) -> list[dict]:
    today = today or date.today()
    earliest = date(today.year - LOOKBACK_YEARS + 1, 1, 1)
    revenue_by_period: dict[date, float] = {}
    for row in financial_rows:
        period = _as_date(row.get("date"))
        if period is None or (period.month, period.day) not in PERIOD_NAMES or period < earliest:
            continue
        amount = _num(row.get("revenue"))
        if amount is None:
            continue
        revenue_by_period[period] = amount

    caps = []
    for row in cap_rows:
        traded = _as_date(row.get("date"))
        amount = _num(row.get("market_cap"))
        if traded is None or amount is None:
            continue
        caps.append((traded, amount))
    caps.sort(key=lambda item: item[0])

    periods = sorted(revenue_by_period)
    if caps:
        first_cap = caps[0][0]
        last_cap = caps[-1][0]
        extra = _period_ends_between(max(earliest, first_cap), min(today, last_cap))
        periods = sorted(set(periods).union(extra))
    periods = [period for period in periods if period >= earliest and period <= today]

    points = []
    for period in periods:
        revenue = revenue_by_period.get(period) if (period.month, period.day) == (12, 31) else None
        points.append(
            {
                "period": period.isoformat(),
                "label": f"{period.year}{PERIOD_NAMES[(period.month, period.day)]}",
                "revenue": revenue,
                "market_cap": _market_cap_on(caps, period),
            }
        )
    return [point for point in points if point["revenue"] is not None or point["market_cap"] is not None]


def _fetch_trend(code: str) -> dict:
    import akshare as ak

    financial = _try(lambda: ak.stock_financial_analysis_indicator_em(symbol=_secucode(code)))
    valuation = _try(lambda: ak.stock_value_em(symbol=code))
    points = build_trend(_financial_rows(financial), _cap_rows(valuation))
    error = None if points else "暂时无法获取营收或市值序列"
    return {"code": code, "points": points, "error": error}


def _financial_rows(frame) -> list[dict]:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return []
    if "REPORT_DATE" not in frame.columns or "TOTALOPERATEREVE" not in frame.columns:
        return []
    rows = []
    for _, item in frame.iterrows():
        rows.append({"date": item.get("REPORT_DATE"), "revenue": item.get("TOTALOPERATEREVE")})
    return rows


def _cap_rows(frame) -> list[dict]:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return []
    if "数据日期" not in frame.columns or "总市值" not in frame.columns:
        return []
    rows = []
    for _, item in frame.iterrows():
        rows.append({"date": item.get("数据日期"), "market_cap": item.get("总市值")})
    return rows


def _period_ends_between(start: date, end: date) -> list[date]:
    periods = []
    for year in range(start.year, end.year + 1):
        for month, day in PERIOD_NAMES:
            current = date(year, month, day)
            if start <= current <= end:
                periods.append(current)
    return periods


def _market_cap_on(caps: list[tuple[date, float]], period: date) -> float | None:
    chosen = None
    for traded, amount in caps:
        if traded <= period:
            chosen = amount
        else:
            break
    return chosen


def _as_date(value) -> date | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value)[:10]
    try:
        return date.fromisoformat(text)
    except ValueError:
        return None


def _num(value) -> float | None:
    try:
        if value is None or pd.isna(value):
            return None
    except TypeError:
        if value is None:
            return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number != number:
        return None
    return number


def _try(fn):
    try:
        return fn()
    except Exception:
        return None
