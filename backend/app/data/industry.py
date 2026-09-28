import re
import statistics

import pandas as pd
import requests

from app.data.cache import get_blob_cached, set_blob_cached
from app.data.fetcher import QuoteError

TREE_KEY = "sw-industry-tree"


def get_industry_tree() -> dict:
    cached = get_blob_cached(TREE_KEY)
    if cached is not None:
        return cached
    payload = _build_tree()
    set_blob_cached(TREE_KEY, payload)
    return payload


def list_industry_stocks(code: str) -> dict:
    tree = get_industry_tree()
    node = tree["index"].get(code)
    if node is None:
        raise QuoteError("没有这个行业")
    if node["level"] == 1:
        raise QuoteError("请先选择细分行业")
    codes = [code] if node["level"] == 3 else node["child_codes"]
    stocks: list[dict] = []
    for child in codes:
        child_node = tree["index"][child]
        stocks.extend(_constituents(child, child_node["name"]))
    stocks.sort(key=lambda item: item.get("market_cap") or 0, reverse=True)
    return {
        "code": code,
        "name": node["name"],
        "level": node["level"],
        "stocks": stocks,
    }


def attach_peers(snapshot: dict, preferred_l3: str | None) -> dict:
    try:
        tree = get_industry_tree()
    except Exception:
        tree = {"index": {}}
    l3 = _resolve_l3(snapshot["code"], preferred_l3, tree)
    industry = _industry_path(l3, tree) if l3 else None
    peers = _constituents(l3, industry["l3_name"]) if l3 and industry else []
    stats = peer_stats(peers, snapshot["code"])
    enriched = dict(snapshot)
    enriched["industry"] = industry
    enriched["peer_count"] = stats["peer_count"]
    enriched["peer_pe_median"] = stats["peer_pe_median"]
    enriched["peer_pb_median"] = stats["peer_pb_median"]
    enriched["peers"] = stats["peers"]
    return enriched


def peer_stats(peers: list[dict], self_code: str) -> dict:
    others = [item for item in peers if item.get("code") != self_code]
    pes = [item["pe"] for item in others if item.get("pe") is not None and item["pe"] > 0]
    pbs = [item["pb"] for item in others if item.get("pb") is not None and item["pb"] > 0]
    shown = sorted(others, key=lambda item: item.get("market_cap") or 0, reverse=True)[:40]
    return {
        "peer_count": len(others),
        "peer_pe_median": float(statistics.median(pes)) if len(pes) >= 3 else None,
        "peer_pb_median": float(statistics.median(pbs)) if len(pbs) >= 3 else None,
        "peers": shown,
    }


def _build_tree() -> dict:
    import akshare as ak

    first = ak.sw_index_first_info()
    second = ak.sw_index_second_info()
    third = ak.sw_index_third_info()
    industries = []
    index: dict[str, dict] = {}
    l2_by_name: dict[str, dict] = {}
    for _, row in first.iterrows():
        node = _node(row, 1)
        node["children"] = []
        industries.append(node)
        index[node["code"]] = {**node, "child_codes": []}
    l1_by_name = {item["name"]: item for item in industries}
    for _, row in second.iterrows():
        node = _node(row, 2)
        parent = l1_by_name.get(_text(row.get("上级行业")))
        if parent is None:
            continue
        node["children"] = []
        parent["children"].append(node)
        index[parent["code"]]["child_codes"].append(node["code"])
        index[node["code"]] = {**node, "child_codes": [], "parent": parent["code"]}
        l2_by_name[node["name"]] = node
    for _, row in third.iterrows():
        node = _node(row, 3)
        parent = l2_by_name.get(_text(row.get("上级行业")))
        if parent is None:
            continue
        parent["children"].append(node)
        index[parent["code"]]["child_codes"].append(node["code"])
        index[node["code"]] = {**node, "child_codes": [], "parent": parent["code"]}
    return {"industries": industries, "index": index}


def _node(row, level: int) -> dict:
    count = row.get("成份个数")
    return {
        "code": _text(row.get("行业代码")),
        "name": _text(row.get("行业名称")),
        "level": level,
        "count": None if pd.isna(count) else int(count),
    }


def _constituents(code: str, name: str) -> list[dict]:
    key = f"sw-cons:{code}"
    cached = get_blob_cached(key)
    if cached is not None:
        return cached["stocks"]
    import akshare as ak

    frame = ak.sw_index_third_cons(symbol=code)
    stocks = _stocks_from_frame(frame, code, name)
    set_blob_cached(key, {"stocks": stocks})
    return stocks


def _stocks_from_frame(frame, industry_code: str, industry_name: str) -> list[dict]:
    if not isinstance(frame, pd.DataFrame) or frame.empty:
        return []
    stocks = []
    for _, row in frame.iterrows():
        raw = _text(row.get("股票代码"))
        code = raw.split(".")[0]
        if not re.fullmatch(r"\d{6}", code):
            continue
        stocks.append(
            {
                "code": code,
                "name": _text(row.get("股票简称")),
                "price": _num(row.get("价格")),
                "pe": _positive(_num(row.get("市盈率ttm"))),
                "pb": _positive(_num(row.get("市净率"))),
                "dividend_yield": _percent(_num(row.get("股息率"))),
                "roe": _percent(_num(row.get("ROE(%)"))),
                "market_cap": _num(row.get("市值")),
                "industry_code": industry_code,
                "industry_name": industry_name,
            }
        )
    return stocks


def _resolve_l3(code: str, preferred: str | None, tree: dict) -> str | None:
    index = tree.get("index") or {}
    if preferred and preferred in index and index[preferred]["level"] == 3:
        return preferred
    cached = get_blob_cached(f"sw-map:{code}")
    if cached and cached.get("l3") in index:
        return cached["l3"]
    try:
        response = requests.get(
            f"https://legulegu.com/s/{code}",
            timeout=15,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        response.raise_for_status()
    except requests.RequestException:
        return None
    for match in re.findall(r"85\d{4}\.SI", response.text):
        if match in index and index[match]["level"] == 3:
            set_blob_cached(f"sw-map:{code}", {"l3": match})
            return match
    return None


def _industry_path(l3: str, tree: dict) -> dict | None:
    index = tree.get("index") or {}
    third = index.get(l3)
    if third is None:
        return None
    second = index.get(third.get("parent"))
    first = index.get(second.get("parent")) if second else None
    return {
        "l1_code": None if first is None else first["code"],
        "l1_name": None if first is None else first["name"],
        "l2_code": None if second is None else second["code"],
        "l2_name": None if second is None else second["name"],
        "l3_code": third["code"],
        "l3_name": third["name"],
    }


def _text(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value).strip()


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


def _positive(value: float | None) -> float | None:
    if value is None or value <= 0:
        return None
    return value


def _percent(value: float | None) -> float | None:
    if value is None:
        return None
    if abs(value) > 1:
        return value / 100
    return value
