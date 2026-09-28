import math
import re
from datetime import date

import requests

from app.data.cache import get_report_cached, set_report_cached
from app.data.fetcher import QuoteError

PERIODS = {
    "一季度报告全文": ("一季报", 1),
    "半年度报告全文": ("半年报", 2),
    "三季度报告全文": ("三季报", 3),
    "年度报告全文": ("年报", 4),
}
YEAR_PATTERN = re.compile(r"((?:19|20)\d{2})年")


def get_reports(code: str) -> dict:
    normalized = code.strip()
    if not re.fullmatch(r"\d{6}", normalized):
        raise QuoteError("请输入 6 位 A 股代码")
    cached = get_report_cached(normalized)
    if cached is not None:
        return cached
    try:
        reports = fetch_periodic_reports(normalized)
    except requests.RequestException:
        return {"code": normalized, "reports": [], "error": "暂时无法获取财报链接"}
    payload = {"code": normalized, "reports": reports}
    set_report_cached(normalized, payload)
    return payload


def fetch_periodic_reports(code: str) -> list[dict]:
    url = "https://np-anotice-stock.eastmoney.com/api/security/ann"
    params = {
        "sr": "-1",
        "page_size": "100",
        "page_index": "1",
        "ann_type": "A",
        "client_source": "web",
        "f_node": "1",
        "s_node": "0",
        "stock_list": code,
        "begin_time": "2000-01-01",
        "end_time": date.today().isoformat(),
    }
    collected: list[dict] = []
    page = 1
    total_pages = 1
    while page <= total_pages and page <= 20:
        params["page_index"] = str(page)
        response = requests.get(url, params=params, timeout=20)
        response.raise_for_status()
        data = response.json().get("data") or {}
        total_hits = int(data.get("total_hits") or 0)
        total_pages = max(1, math.ceil(total_hits / 100))
        for item in data.get("list") or []:
            parsed = parse_notice(code, item)
            if parsed is not None:
                collected.append(parsed)
        if not data.get("list"):
            break
        page += 1
    return dedupe_reports(collected)


def parse_notice(code: str, item: dict) -> dict | None:
    columns = item.get("columns") or []
    if not columns:
        return None
    period = PERIODS.get(columns[0].get("column_name"))
    if period is None:
        return None
    title = str(item.get("title") or "")
    matched = YEAR_PATTERN.search(title)
    if matched is None:
        return None
    art_code = item.get("art_code")
    if not art_code:
        return None
    label, order = period
    notice_date = str(item.get("notice_date") or "")[:10]
    return {
        "year": int(matched.group(1)),
        "period": label,
        "order": order,
        "title": title,
        "date": notice_date,
        "url": f"https://data.eastmoney.com/notices/detail/{code}/{art_code}.html",
    }


def dedupe_reports(items: list[dict]) -> list[dict]:
    chosen: dict[tuple[int, str], dict] = {}
    for item in items:
        key = (item["year"], item["period"])
        current = chosen.get(key)
        if current is None or item["date"] >= current["date"]:
            chosen[key] = item
    reports = sorted(chosen.values(), key=lambda item: (-item["year"], item["order"]))
    for report in reports:
        report.pop("order", None)
    return reports
