from app.valuation.models import ModelResult

NAV_NOTE = "以最新年报每股净资产作为账面净资产价值，未做重置成本调整"


def value_nav(bps: float | None) -> ModelResult:
    assumptions = {"每股净资产": bps, "说明": NAV_NOTE}
    if bps is None or bps <= 0:
        return ModelResult("净资产", False, None, assumptions, "净资产不为正")
    return ModelResult("净资产", True, bps, assumptions, None)
