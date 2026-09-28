import statistics

from app.valuation.models import ModelResult


def value_comps(
    eps: float | None,
    bps: float | None,
    peer_pe: float | None,
    peer_pb: float | None,
    peer_count: int | None,
    industry_name: str | None,
) -> ModelResult:
    assumptions = {
        "同行业": industry_name,
        "可比公司数": peer_count,
        "行业PE中位数": peer_pe,
        "行业PB中位数": peer_pb,
        "每股收益TTM": eps,
        "每股净资产": bps,
    }
    if peer_count is None or peer_count < 3:
        return ModelResult("类比", False, None, assumptions, "同行业可比公司不足")
    prices = []
    if eps is not None and eps > 0 and peer_pe is not None and peer_pe > 0:
        prices.append(eps * peer_pe)
        assumptions["类比PE价格"] = eps * peer_pe
    if bps is not None and bps > 0 and peer_pb is not None and peer_pb > 0:
        prices.append(bps * peer_pb)
        assumptions["类比PB价格"] = bps * peer_pb
    if not prices:
        return ModelResult("类比", False, None, assumptions, "缺少可比倍数或盈利、净资产")
    return ModelResult("类比", True, float(statistics.median(prices)), assumptions, None)
