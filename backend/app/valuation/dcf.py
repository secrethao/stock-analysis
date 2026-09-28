from app.valuation.models import ModelResult

NET_DEBT_NOTE = "净负债按 0 计；自由现金流近似为经营现金流，未扣除资本开支"


def default_forecast_growth(revenue_cagr_3y: float | None) -> float | None:
    if revenue_cagr_3y is None:
        return None
    return min(0.15, max(0.0, revenue_cagr_3y / 2))


def value_dcf(
    fcf0: float | None,
    growth: float | None,
    discount: float | None,
    terminal_growth: float | None,
    shares: float | None,
    net_debt: float = 0,
    years: int = 5,
) -> ModelResult:
    assumptions = {
        "基期经营现金流": fcf0,
        "预测增速": growth,
        "折现率": discount,
        "永续增速": terminal_growth,
        "总股本": shares,
        "净负债": net_debt,
        "说明": NET_DEBT_NOTE,
    }
    if fcf0 is None or fcf0 <= 0:
        return ModelResult("DCF", False, None, assumptions, "经营现金流不为正")
    if growth is None:
        return ModelResult("DCF", False, None, assumptions, "无法估计营收增速")
    if shares is None or shares <= 0:
        return ModelResult("DCF", False, None, assumptions, "总股本无效")
    if discount is None or terminal_growth is None or discount <= terminal_growth:
        return ModelResult("DCF", False, None, assumptions, "折现率不高于永续增速")
    if growth <= -1:
        return ModelResult("DCF", False, None, assumptions, "预测增速无效")

    fcf = fcf0
    pv_sum = 0.0
    for year in range(1, years + 1):
        fcf *= 1 + growth
        pv_sum += fcf / (1 + discount) ** year
    terminal = fcf * (1 + terminal_growth) / (discount - terminal_growth)
    pv_terminal = terminal / (1 + discount) ** years
    equity = pv_sum + pv_terminal - net_debt
    assumptions["第5年自由现金流"] = fcf
    assumptions["股权价值"] = equity
    if equity <= 0:
        return ModelResult("DCF", False, None, assumptions, "股权价值不为正")
    return ModelResult("DCF", True, equity / shares, assumptions, None)
