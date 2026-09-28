import math
import re
import time
from datetime import date, timedelta

import pandas as pd

from app.data.cache import get_cached, set_cached
from app.data.dividends import summarize_dividend_frame

MIN_PE_SAMPLES = 60


class QuoteError(Exception):
    pass


def get_quote(code: str) -> dict:
    normalized = code.strip()
    if not re.fullmatch(r"\d{6}", normalized):
        raise QuoteError("请输入 6 位 A 股代码")
    cached = get_cached(normalized)
    if cached is not None and "dps" in cached:
        return cached
    payload = _fetch(normalized)
    set_cached(normalized, payload)
    return payload


def _fetch(code: str) -> dict:
    import akshare as ak

    info = _try(lambda: ak.stock_individual_info_em(symbol=code))
    hist = _try(
        lambda: ak.stock_zh_a_hist(
            symbol=code,
            period="daily",
            start_date=(date.today() - timedelta(days=30)).strftime("%Y%m%d"),
            end_date=date.today().strftime("%Y%m%d"),
            adjust="qfq",
        )
    )
    valuation = _try(lambda: ak.stock_value_em(symbol=code))
    financial = _try(lambda: ak.stock_financial_analysis_indicator_em(symbol=_secucode(code)))
    dividend = _try(lambda: ak.stock_fhps_detail_em(symbol=code))

    price, price_date = _price(hist, valuation)
    if price is None:
        raise QuoteError("无法获取行情，请确认代码是否为有效 A 股")

    name = _name(info, financial) or code
    shares = _shares(info, valuation)
    pe_ttm, pe_median = _pe_stats(valuation)
    annual = _annual_reports(financial)

    report_period = None
    bps = None
    roe_3y = None
    debt_ratio = None
    operating_cashflow = None
    net_profit_latest = None
    net_profit_3y_ago = None
    revenue_cagr_3y = None

    if annual is not None and not annual.empty:
        latest = annual.iloc[0]
        report_period = latest["REPORT_DATE"].date().isoformat()
        bps = _num(latest.get("BPS"))
        debt_ratio = _as_ratio(latest.get("ZCFZL"))
        net_profit_latest = _num(latest.get("PARENTNETPROFIT"))
        ocf_ps = _num(latest.get("MGJYXJJE"))
        if ocf_ps is not None and shares is not None:
            operating_cashflow = ocf_ps * shares
        roe_3y = _roe_average(annual)
        older = _years_before(annual, latest["REPORT_DATE"], 3)
        if older is not None:
            net_profit_3y_ago = _num(older.get("PARENTNETPROFIT"))
            revenue_cagr_3y = _cagr(
                _num(latest.get("TOTALOPERATEREVE")),
                _num(older.get("TOTALOPERATEREVE")),
            )

    eps = price / pe_ttm if pe_ttm is not None and pe_ttm > 0 else None
    dps, dividend_cagr = summarize_dividend_frame(dividend)
    return {
        "code": code,
        "name": name,
        "price": price,
        "price_date": price_date,
        "report_period": report_period,
        "shares": shares,
        "eps": eps,
        "bps": bps,
        "pe_ttm": pe_ttm,
        "pe_median_5y": pe_median,
        "roe_3y": roe_3y,
        "debt_ratio": debt_ratio,
        "operating_cashflow": operating_cashflow,
        "net_profit_latest": net_profit_latest,
        "net_profit_3y_ago": net_profit_3y_ago,
        "revenue_cagr_3y": revenue_cagr_3y,
        "dps": dps,
        "dividend_cagr": dividend_cagr,
    }


def _secucode(code: str) -> str:
    if code.startswith(("6", "9")):
        return f"{code}.SH"
    if code.startswith(("4", "8")):
        return f"{code}.BJ"
    return f"{code}.SZ"


def _try(fn):
    last_error = None
    for _ in range(2):
        try:
            return fn()
        except Exception as exc:
            last_error = exc
            time.sleep(0.4)
    return None if last_error is not None else None


def _price(hist, valuation) -> tuple[float | None, str | None]:
    if isinstance(hist, pd.DataFrame) and not hist.empty and "收盘" in hist.columns:
        row = hist.dropna(subset=["收盘"]).iloc[-1]
        close = _num(row["收盘"])
        if close is not None and close > 0:
            traded = row["日期"]
            return close, traded.isoformat() if hasattr(traded, "isoformat") else str(traded)
    if isinstance(valuation, pd.DataFrame) and not valuation.empty:
        row = valuation.dropna(subset=["当日收盘价"]).iloc[-1]
        close = _num(row["当日收盘价"])
        if close is not None and close > 0:
            traded = row["数据日期"]
            return close, traded.isoformat() if hasattr(traded, "isoformat") else str(traded)
    return None, None


def _name(info, financial) -> str | None:
    if isinstance(info, pd.DataFrame) and not info.empty and "item" in info.columns:
        matched = info.loc[info["item"] == "股票简称", "value"]
        if not matched.empty and pd.notna(matched.iloc[0]):
            return str(matched.iloc[0])
    if isinstance(financial, pd.DataFrame) and not financial.empty:
        value = financial.iloc[0].get("SECURITY_NAME_ABBR")
        if pd.notna(value):
            return str(value)
    return None


def _shares(info, valuation) -> float | None:
    if isinstance(info, pd.DataFrame) and not info.empty and "item" in info.columns:
        matched = info.loc[info["item"] == "总股本", "value"]
        shares = _num(matched.iloc[0]) if not matched.empty else None
        if shares is not None and shares > 0:
            return shares
    if isinstance(valuation, pd.DataFrame) and not valuation.empty and "总股本" in valuation.columns:
        shares = _num(valuation.iloc[-1]["总股本"])
        if shares is not None and shares > 0:
            return shares
    return None


def _pe_stats(valuation) -> tuple[float | None, float | None]:
    if not isinstance(valuation, pd.DataFrame) or valuation.empty or "PE(TTM)" not in valuation.columns:
        return None, None
    frame = valuation.dropna(subset=["PE(TTM)", "数据日期"]).copy()
    if frame.empty:
        return None, None
    latest_pe = _num(frame.iloc[-1]["PE(TTM)"])
    latest_date = pd.to_datetime(frame.iloc[-1]["数据日期"])
    window = frame[pd.to_datetime(frame["数据日期"]) >= latest_date - pd.Timedelta(days=365 * 5)]
    positive = window[window["PE(TTM)"] > 0]["PE(TTM)"]
    median = float(positive.median()) if len(positive) >= MIN_PE_SAMPLES else None
    if median is not None and (math.isnan(median) or median <= 0):
        median = None
    if latest_pe is not None and latest_pe <= 0:
        latest_pe = None
    return latest_pe, median


def _annual_reports(financial):
    if not isinstance(financial, pd.DataFrame) or financial.empty or "REPORT_DATE" not in financial.columns:
        return None
    frame = financial.copy()
    frame["REPORT_DATE"] = pd.to_datetime(frame["REPORT_DATE"], errors="coerce")
    annual = frame[frame["REPORT_DATE"].dt.month.eq(12) & frame["REPORT_DATE"].dt.day.eq(31)]
    if annual.empty:
        return None
    return annual.sort_values("REPORT_DATE", ascending=False)


def _roe_average(annual: pd.DataFrame) -> float | None:
    values = []
    for _, row in annual.head(3).iterrows():
        ratio = _as_ratio(row.get("ROEJQ"))
        if ratio is None:
            return None
        values.append(ratio)
    if len(values) < 3:
        return None
    return sum(values) / 3


def _years_before(annual: pd.DataFrame, latest: pd.Timestamp, years: int):
    target_year = latest.year - years
    matched = annual[annual["REPORT_DATE"].dt.year.eq(target_year)]
    if matched.empty:
        return None
    return matched.iloc[0]


def _cagr(latest: float | None, older: float | None) -> float | None:
    if latest is None or older is None or latest <= 0 or older <= 0:
        return None
    return (latest / older) ** (1 / 3) - 1


def _as_ratio(value) -> float | None:
    number = _num(value)
    if number is None:
        return None
    if abs(number) > 1:
        return number / 100
    return number


def _num(value) -> float | None:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    try:
        if pd.isna(value):
            return None
    except TypeError:
        pass
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if math.isnan(number) or math.isinf(number):
        return None
    return number
