import re
import statistics
import time
from datetime import date, datetime

import pandas as pd
import requests

from app.data.cache import get_blob_cached, set_blob_cached
from app.data.fetcher import QuoteError, _secucode

QUARTER_ENDS = {(3, 31), (6, 30), (9, 30), (12, 31)}
ASSET_ORDER = ("现金", "应收款", "预付款", "存货", "其它流动", "长期投资", "固定资产", "无形&商誉", "其它固定")
LIABILITY_ORDER = ("短期借款", "应付款", "预收款", "薪酬&税", "其它流动", "长期借款", "其它非流动")


def get_charts(code: str) -> dict:
    normalized = code.strip()
    if not re.fullmatch(r"\d{6}", normalized):
        raise QuoteError("请输入 6 位 A 股代码")
    cached = get_blob_cached(f"charts:v3:{normalized}")
    if cached is not None:
        return cached
    payload = _fetch_charts(normalized)
    if payload["market_cap"] and (payload["revenue"] or payload["pe"] or payload["balance_sheets"]):
        set_blob_cached(f"charts:v3:{normalized}", payload)
    return payload


def build_revenue(reports: list[dict]) -> list[dict]:
    points = []
    for row in reports:
        period = _as_date(row.get("date"))
        amount = _num(row.get("revenue"))
        if period is None or amount is None or amount <= 0:
            continue
        points.append({"date": period.isoformat(), "value": amount})
    points.sort(key=lambda item: item["date"])
    return points


def build_quarter_profits(reports: list[dict]) -> list[tuple[date, float]]:
    cumulative: dict[date, float] = {}
    for row in reports:
        period = _as_date(row.get("date"))
        amount = _num(row.get("profit"))
        if period is None or amount is None or (period.month, period.day) not in QUARTER_ENDS:
            continue
        cumulative[period] = amount
    quarters = []
    by_year: dict[int, list[tuple[date, float]]] = {}
    for period in sorted(cumulative):
        by_year.setdefault(period.year, []).append((period, cumulative[period]))
    for year in sorted(by_year):
        previous = 0.0
        for period, amount in by_year[year]:
            quarters.append((period, amount - previous))
            previous = amount
    return quarters


def build_ttm_profits(quarters: list[tuple[date, float]]) -> list[dict]:
    ordered = sorted(quarters, key=lambda item: item[0])
    points = []
    for index in range(3, len(ordered)):
        window = ordered[index - 3 : index + 1]
        if not _consecutive_quarters(window):
            continue
        total = sum(amount for _, amount in window)
        points.append({"date": window[-1][0].isoformat(), "value": total})
    return points


def build_market_caps(prices: list[dict], shares: list[dict]) -> list[dict]:
    capital = sorted(
        (
            (_as_date(row.get("date")), _num(row.get("shares")))
            for row in shares
        ),
        key=lambda item: item[0] or date.min,
    )
    capital = [(day, amount) for day, amount in capital if day is not None and amount is not None and amount > 0]
    points = []
    cursor = 0
    current = None
    for row in sorted(prices, key=lambda item: item.get("date") or ""):
        traded = _as_date(row.get("date"))
        price = _num(row.get("price"))
        if traded is None or price is None or price <= 0:
            continue
        while cursor < len(capital) and capital[cursor][0] <= traded:
            current = capital[cursor][1]
            cursor += 1
        if current is None:
            continue
        points.append({"date": traded.isoformat(), "value": price * current})
    return points


def build_pe(market_caps: list[dict], ttm_profits: list[dict]) -> list[dict]:
    profits = sorted(ttm_profits, key=lambda item: item["date"])
    points = []
    cursor = 0
    current = None
    for row in sorted(market_caps, key=lambda item: item["date"]):
        while cursor < len(profits) and profits[cursor]["date"] <= row["date"]:
            current = profits[cursor]["value"]
            cursor += 1
        if current is None or current <= 0:
            continue
        points.append({"date": row["date"], "value": row["value"] / current})
    return points


def pe_bands(values: list[float]) -> dict:
    usable = [value for value in values if value is not None and value > 0]
    if len(usable) < 2:
        return {"mean": None, "std": None, "high": None, "low": None}
    mean = statistics.fmean(usable)
    deviation = statistics.pstdev(usable)
    return {
        "mean": mean,
        "std": deviation,
        "high": mean + deviation,
        "low": mean - deviation,
    }


def build_balance_sheet(row: dict) -> list[dict]:
    trade = _num(row.get("FVTPL_FINASSET"))
    if trade is None:
        trade = _num(row.get("TRADE_FINASSET")) or 0.0
    cash = _sum_present(
        row,
        "MONETARYFUNDS",
        "SETTLE_EXCESS_RESERVE",
        "LEND_FUND",
    ) + trade
    receivables = _combined(row, "NOTE_ACCOUNTS_RECE", ("NOTE_RECE", "ACCOUNTS_RECE")) + (
        _num(row.get("TOTAL_OTHER_RECE")) or 0.0
    )
    prepayment = _sum_present(row, "PREPAYMENT", "LOAN_ADVANCE")
    inventory = _num(row.get("INVENTORY")) or 0.0
    other_current_asset = _sum_present(
        row,
        "NONCURRENT_ASSET_1YEAR",
        "OTHER_CURRENT_ASSET",
        "CONTRACT_ASSET",
        "HOLDSALE_ASSET",
    )
    long_investment = _sum_present(
        row,
        "LONG_EQUITY_INVEST",
        "OTHER_EQUITY_INVEST",
        "OTHER_NONCURRENT_FINASSET",
        "CREDITOR_INVEST",
        "INVEST_REALESTATE",
        "AVAILABLE_SALE_FINASSET",
        "HOLD_MATURITY_INVEST",
    )
    fixed_asset = _sum_present(row, "FIXED_ASSET", "CIP", "PROJECT_MATERIAL", "FIXED_ASSET_DISPOSAL")
    intangible = _sum_present(row, "INTANGIBLE_ASSET", "GOODWILL", "DEVELOP_EXPENSE", "USERIGHT_ASSET")
    other_fixed = _sum_present(
        row,
        "DEFER_TAX_ASSET",
        "OTHER_NONCURRENT_ASSET",
        "LONG_PREPAID_EXPENSE",
        "OIL_GAS_ASSET",
        "LONG_RECE",
    )
    short_loan = _sum_present(
        row,
        "SHORT_LOAN",
        "NONCURRENT_LIAB_1YEAR",
        "SHORT_BOND_PAYABLE",
        "SHORT_FIN_PAYABLE",
        "BORROW_FUND",
    )
    payable = _combined(row, "NOTE_ACCOUNTS_PAYABLE", ("NOTE_PAYABLE", "ACCOUNTS_PAYABLE")) + (
        _num(row.get("TOTAL_OTHER_PAYABLE")) or 0.0
    )
    advance = _sum_present(row, "ADVANCE_RECEIVABLES", "CONTRACT_LIAB", "ACCEPT_DEPOSIT_INTERBANK")
    payroll_tax = _sum_present(row, "STAFF_SALARY_PAYABLE", "TAX_PAYABLE")
    other_current_liability = _sum_present(row, "OTHER_CURRENT_LIAB")
    long_loan = _sum_present(row, "LONG_LOAN", "BOND_PAYABLE")
    noncurrent = _num(row.get("TOTAL_NONCURRENT_LIAB"))
    other_noncurrent = (noncurrent - long_loan) if noncurrent is not None else _sum_present(
        row,
        "LEASE_LIAB",
        "LONG_PAYABLE",
        "DEFER_TAX_LIAB",
        "OTHER_NONCURRENT_LIAB",
    )
    assets = {
        "现金": cash,
        "应收款": receivables,
        "预付款": prepayment,
        "存货": inventory,
        "其它流动": other_current_asset,
        "长期投资": long_investment,
        "固定资产": fixed_asset,
        "无形&商誉": intangible,
        "其它固定": other_fixed,
    }
    liabilities = {
        "短期借款": short_loan,
        "应付款": payable,
        "预收款": advance,
        "薪酬&税": payroll_tax,
        "其它流动": other_current_liability,
        "长期借款": long_loan,
        "其它非流动": max(other_noncurrent, 0.0),
    }
    items = [{"name": name, "value": assets[name], "side": "asset"} for name in ASSET_ORDER]
    items.extend({"name": name, "value": liabilities[name], "side": "liability"} for name in LIABILITY_ORDER)
    return items


def _fetch_charts(code: str) -> dict:
    secucode = _secucode(code)
    reports = _safe(_financial_reports, secucode, [])
    prices, listed_name = _safe(_prices, code, ([], None))
    shares = _safe(_shares, secucode, [])
    revenue = build_revenue(reports)
    market_cap = build_market_caps(prices, shares)
    ttm = build_ttm_profits(build_quarter_profits(reports))
    pe = build_pe(market_cap, ttm)
    bands = pe_bands([point["value"] for point in pe])
    name = listed_name or next((row.get("name") for row in reports if row.get("name")), None) or code
    listed_on = prices[0]["date"] if prices else (revenue[0]["date"] if revenue else None)
    if listed_on:
        revenue = [point for point in revenue if point["date"] >= listed_on]
    balance_sheets = []
    balance_error = None
    try:
        balance_sheets = _balance_sheets(secucode)
    except Exception:
        balance_error = "暂时无法获取资产负债表"
    error = None
    if not revenue and not market_cap:
        error = "暂时无法获取营收或市值序列"
    elif not pe:
        error = None
    return {
        "code": code,
        "name": name,
        "listed_on": listed_on,
        "revenue": revenue,
        "market_cap": market_cap,
        "pe": pe,
        "pe_mean": bands["mean"],
        "pe_std": bands["std"],
        "pe_high": bands["high"],
        "pe_low": bands["low"],
        "balance_sheets": balance_sheets,
        "error": error,
        "balance_error": balance_error,
    }


def _financial_reports(secucode: str) -> list[dict]:
    rows = []
    page = 1
    total = None
    while page <= 10:
        payload = _get_json(
            "https://datacenter.eastmoney.com/securities/api/data/get",
            {
                "type": "RPT_F10_FINANCE_MAINFINADATA",
                "sty": "APP_F10_MAINFINADATA",
                "quoteColumns": "",
                "filter": f'(SECUCODE="{secucode}")',
                "p": str(page),
                "ps": "200",
                "sr": "1",
                "st": "REPORT_DATE",
                "source": "HSF10",
                "client": "PC",
            },
        )
        result = (payload or {}).get("result") or {}
        chunk = result.get("data") or []
        total = result.get("count", total)
        for item in chunk:
            rows.append(
                {
                    "date": item.get("REPORT_DATE"),
                    "revenue": item.get("TOTALOPERATEREVE"),
                    "profit": item.get("PARENTNETPROFIT"),
                    "name": item.get("SECURITY_NAME_ABBR"),
                }
            )
        if not chunk or (total is not None and len(rows) >= int(total)):
            break
        page += 1
    return rows


def _prices(code: str) -> tuple[list[dict], str | None]:
    market = "1" if code.startswith(("6", "9")) else "0"
    payload = _get_json(
        "https://push2his.eastmoney.com/api/qt/stock/kline/get",
        {
            "secid": f"{market}.{code}",
            "klt": "101",
            "fqt": "0",
            "beg": "0",
            "end": "20500101",
            "fields1": "f1,f2,f3,f4,f5,f6",
            "fields2": "f51,f53",
        },
    )
    data = (payload or {}).get("data") or {}
    points = []
    for line in data.get("klines") or []:
        parts = str(line).split(",")
        if len(parts) < 2:
            continue
        points.append({"date": parts[0], "price": parts[1]})
    return points, data.get("name")


def _shares(secucode: str) -> list[dict]:
    payload = _get_json(
        "https://datacenter.eastmoney.com/securities/api/data/v1/get",
        {
            "reportName": "RPT_F10_EH_EQUITY",
            "columns": "SECUCODE,END_DATE,TOTAL_SHARES",
            "quoteColumns": "",
            "filter": f'(SECUCODE="{secucode}")',
            "pageNumber": "1",
            "pageSize": "500",
            "sortTypes": "1",
            "sortColumns": "END_DATE",
            "source": "HSF10",
            "client": "PC",
        },
    )
    result = (payload or {}).get("result") or {}
    rows = list(result.get("data") or [])
    pages = int(result.get("pages") or 1)
    for page in range(2, pages + 1):
        extra = _get_json(
            "https://datacenter.eastmoney.com/securities/api/data/v1/get",
            {
                "reportName": "RPT_F10_EH_EQUITY",
                "columns": "SECUCODE,END_DATE,TOTAL_SHARES",
                "quoteColumns": "",
                "filter": f'(SECUCODE="{secucode}")',
                "pageNumber": str(page),
                "pageSize": "500",
                "sortTypes": "1",
                "sortColumns": "END_DATE",
                "source": "HSF10",
                "client": "PC",
            },
        )
        rows.extend(((extra or {}).get("result") or {}).get("data") or [])
    return [{"date": row.get("END_DATE"), "shares": row.get("TOTAL_SHARES")} for row in rows]


def _balance_sheets(secucode: str) -> list[dict]:
    em_code = secucode.replace(".", "")
    if em_code.endswith("SH"):
        em_code = "SH" + em_code[:6]
    elif em_code.endswith("SZ"):
        em_code = "SZ" + em_code[:6]
    elif em_code.endswith("BJ"):
        em_code = "BJ" + em_code[:6]
    page = None
    for _ in range(3):
        try:
            page = requests.get(
                "https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/Index",
                params={"type": "web", "code": em_code.lower()},
                timeout=20,
                headers={"User-Agent": "Mozilla/5.0"},
            )
            page.raise_for_status()
            break
        except Exception:
            page = None
            time.sleep(0.4)
    if page is None:
        return []
    matched = re.search(r'hidctype"[^>]*value="([^"]+)"', page.text)
    company_type = matched.group(1) if matched else "4"
    dates_payload = _get_json(
        "https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/zcfzbDateAjaxNew",
        {"companyType": company_type, "reportDateType": "0", "code": em_code},
    )
    dates = []
    for row in (dates_payload or {}).get("data") or []:
        text = str(row.get("REPORT_DATE") or "")[:10]
        if text:
            dates.append(text)
    dates = sorted(set(dates), reverse=True)[:12]
    sheets = []
    for offset in range(0, len(dates), 5):
        chunk = dates[offset : offset + 5]
        payload = _get_json(
            "https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/zcfzbAjaxNew",
            {
                "companyType": company_type,
                "reportDateType": "0",
                "reportType": "1",
                "dates": ",".join(chunk),
                "code": em_code,
            },
        )
        for row in (payload or {}).get("data") or []:
            period = str(row.get("REPORT_DATE") or "")[:10]
            sheets.append({"date": period, "items": build_balance_sheet(row)})
    sheets.sort(key=lambda item: item["date"], reverse=True)
    return sheets


def _consecutive_quarters(window: list[tuple[date, float]]) -> bool:
    for (left, _), (right, _) in zip(window, window[1:]):
        gap = (right - left).days
        if gap < 70 or gap > 120:
            return False
    return True


def _combined(row: dict, combined_key: str, parts: tuple[str, ...]) -> float:
    combined = _num(row.get(combined_key))
    if combined is not None:
        return combined
    return sum(_num(row.get(key)) or 0.0 for key in parts)


def _sum_present(row: dict, *keys: str) -> float:
    total = 0.0
    for key in keys:
        value = _num(row.get(key))
        if value is not None:
            total += value
    return total


def _get_json(url: str, params: dict):
    last_error = None
    for attempt in range(3):
        try:
            response = requests.get(url, params=params, timeout=30)
            response.raise_for_status()
            return response.json()
        except Exception as exc:
            last_error = exc
            time.sleep(0.5 * (attempt + 1))
    raise last_error


def _safe(fn, arg, fallback):
    try:
        return fn(arg)
    except Exception:
        return fallback


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

