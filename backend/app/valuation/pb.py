from app.valuation.models import ModelResult


def value_pb(
    bps: float | None,
    roe_3y: float | None,
    required_return: float | None,
    target_pb: float | None = None,
) -> ModelResult:
    used_pb = target_pb
    derived = False
    if used_pb is None:
        derived = True
        if (
            roe_3y is None
            or roe_3y <= 0
            or required_return is None
            or required_return <= 0
        ):
            assumptions = {
                "每股净资产": bps,
                "近三年平均ROE": roe_3y,
                "要求回报率": required_return,
                "目标PB": None,
            }
            return ModelResult("PB", False, None, assumptions, "ROE不为正或要求回报率无效")
        used_pb = roe_3y / required_return

    assumptions = {
        "每股净资产": bps,
        "近三年平均ROE": roe_3y,
        "要求回报率": required_return,
        "目标PB": used_pb,
        "目标PB来源": "近三年平均ROE / 要求回报率" if derived else "手填",
    }
    if bps is None or bps <= 0:
        return ModelResult("PB", False, None, assumptions, "净资产不为正")
    if used_pb <= 0:
        return ModelResult("PB", False, None, assumptions, "目标市净率无效")
    return ModelResult("PB", True, bps * used_pb, assumptions, None)
