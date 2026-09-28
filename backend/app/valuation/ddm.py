from app.valuation.models import ModelResult


def value_ddm(
    dps: float | None,
    growth: float | None,
    required_return: float | None,
    growth_source: str,
) -> ModelResult:
    assumptions = {
        "最近年度每股分红": dps,
        "分红增速": growth,
        "要求回报率": required_return,
        "分红增速来源": growth_source,
    }
    if dps is None or dps <= 0:
        return ModelResult("股利折现", False, None, assumptions, "没有现金分红")
    if growth is None or growth <= -1:
        return ModelResult("股利折现", False, None, assumptions, "分红增速无效")
    if required_return is None or required_return <= growth:
        return ModelResult("股利折现", False, None, assumptions, "要求回报率不高于分红增速")
    price = dps * (1 + growth) / (required_return - growth)
    return ModelResult("股利折现", True, price, assumptions, None)
