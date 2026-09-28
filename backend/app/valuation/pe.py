from app.valuation.models import ModelResult


def value_pe(eps: float | None, target_pe: float | None) -> ModelResult:
    assumptions = {"每股收益TTM": eps, "目标PE": target_pe}
    if eps is None or eps <= 0:
        return ModelResult("PE", False, None, assumptions, "每股收益不为正")
    if target_pe is None or target_pe <= 0:
        return ModelResult("PE", False, None, assumptions, "历史市盈率不足或目标市盈率无效")
    return ModelResult("PE", True, eps * target_pe, assumptions, None)
