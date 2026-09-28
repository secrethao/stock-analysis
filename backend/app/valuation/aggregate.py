import statistics

from app.valuation.comps import value_comps
from app.valuation.dcf import default_forecast_growth, value_dcf
from app.valuation.ddm import value_ddm
from app.valuation.nav import value_nav
from app.valuation.pb import value_pb
from app.valuation.pe import value_pe

DISCOUNT_GRID = (0.08, 0.10, 0.12)
TERMINAL_GRID = (0.02, 0.03, 0.04)


def quality_checks(
    roe_3y: float | None,
    debt_ratio: float | None,
    operating_cashflow: float | None,
    net_profit_latest: float | None,
    net_profit_3y_ago: float | None,
    roe_threshold: float = 0.10,
) -> dict:
    roe_ok = roe_3y is not None and roe_3y > roe_threshold
    debt_ok = debt_ratio is not None and debt_ratio < 0.60
    cash_ok = operating_cashflow is not None and operating_cashflow > 0
    profit_ok = (
        net_profit_latest is not None
        and net_profit_3y_ago is not None
        and net_profit_latest >= net_profit_3y_ago
    )
    items = [
        {
            "name": "近三年平均ROE",
            "passed": roe_ok,
            "detail": _fmt_pct(roe_3y),
            "rule": f"高于 {_fmt_pct(roe_threshold)}",
        },
        {
            "name": "资产负债率",
            "passed": debt_ok,
            "detail": _fmt_pct(debt_ratio),
            "rule": "低于 60%",
        },
        {
            "name": "经营现金流",
            "passed": cash_ok,
            "detail": _fmt_num(operating_cashflow),
            "rule": "最新年报为正",
        },
        {
            "name": "利润趋势",
            "passed": profit_ok,
            "detail": _profit_detail(net_profit_latest, net_profit_3y_ago),
            "rule": "最近一年不低于三年前",
        },
    ]
    return {"passed": all(item["passed"] for item in items), "items": items}


def sensitivity_grid(
    fcf0: float | None,
    growth: float | None,
    shares: float | None,
) -> list[dict]:
    rows = []
    for discount in DISCOUNT_GRID:
        for terminal in TERMINAL_GRID:
            result = value_dcf(fcf0, growth, discount, terminal, shares, net_debt=0)
            rows.append(
                {
                    "discount_rate": discount,
                    "terminal_growth": terminal,
                    "applicable": result.applicable,
                    "price": result.price,
                    "reason": result.reason,
                }
            )
    return rows


def valuate(quote: dict, assumptions: dict) -> dict:
    target_pe = assumptions.get("target_pe")
    if target_pe is None:
        target_pe = quote.get("pe_median_5y")
    growth = assumptions.get("forecast_growth")
    if growth is None:
        growth = default_forecast_growth(quote.get("revenue_cagr_3y"))
    dividend_growth, dividend_source = _dividend_growth(quote, assumptions)
    industry = quote.get("industry") or {}

    models = [
        value_pe(quote.get("eps"), target_pe),
        value_pb(
            quote.get("bps"),
            quote.get("roe_3y"),
            assumptions.get("required_return", 0.10),
            assumptions.get("target_pb"),
        ),
        value_dcf(
            quote.get("operating_cashflow"),
            growth,
            assumptions.get("discount_rate", 0.10),
            assumptions.get("terminal_growth", 0.03),
            quote.get("shares"),
            net_debt=0,
        ),
        value_ddm(
            quote.get("dps"),
            dividend_growth,
            assumptions.get("required_return", 0.10),
            dividend_source,
        ),
        value_nav(quote.get("bps")),
        value_comps(
            quote.get("eps"),
            quote.get("bps"),
            quote.get("peer_pe_median"),
            quote.get("peer_pb_median"),
            quote.get("peer_count"),
            industry.get("l3_name"),
        ),
    ]
    quality = quality_checks(
        quote.get("roe_3y"),
        quote.get("debt_ratio"),
        quote.get("operating_cashflow"),
        quote.get("net_profit_latest"),
        quote.get("net_profit_3y_ago"),
        assumptions.get("roe_threshold", 0.10),
    )
    summary = _summarize(
        quote.get("price"),
        models,
        quality,
        assumptions.get("margin_threshold", 0.25),
    )
    price = quote.get("price")
    model_rows = []
    for model in models:
        premium = None
        if model.applicable and model.price is not None and price not in (None, 0):
            premium = (model.price - price) / price
        row = model.to_dict()
        row["premium_vs_price"] = premium
        model_rows.append(row)

    return {
        "code": quote.get("code"),
        "name": quote.get("name"),
        "price": price,
        "price_date": quote.get("price_date"),
        "report_period": quote.get("report_period"),
        "industry": quote.get("industry"),
        "peers": quote.get("peers") or [],
        "models": model_rows,
        "quality": quality,
        "sensitivity": sensitivity_grid(
            quote.get("operating_cashflow"),
            growth,
            quote.get("shares"),
        ),
        "assumptions_used": {
            "target_pe": target_pe,
            "target_pb": assumptions.get("target_pb"),
            "required_return": assumptions.get("required_return", 0.10),
            "discount_rate": assumptions.get("discount_rate", 0.10),
            "terminal_growth": assumptions.get("terminal_growth", 0.03),
            "forecast_growth": growth,
            "dividend_growth": dividend_growth,
            "margin_threshold": assumptions.get("margin_threshold", 0.25),
            "roe_threshold": assumptions.get("roe_threshold", 0.10),
        },
        **summary,
    }


def _summarize(price, models, quality, margin_threshold: float) -> dict:
    applicable = [model.price for model in models if model.applicable and model.price is not None]
    if len(applicable) < 2 or price is None:
        return {
            "fair_price": None,
            "fair_low": None,
            "fair_high": None,
            "margin": None,
            "verdict": "证据不足",
        }
    fair = float(statistics.median(applicable))
    if fair == 0:
        return {
            "fair_price": fair,
            "fair_low": min(applicable),
            "fair_high": max(applicable),
            "margin": None,
            "verdict": "证据不足",
        }
    margin = (fair - price) / fair
    if margin >= margin_threshold and quality["passed"]:
        verdict = "低估可关注"
    elif margin >= margin_threshold:
        verdict = "便宜但质量存疑"
    elif margin >= 0:
        verdict = "大致合理"
    else:
        verdict = "偏贵"
    return {
        "fair_price": fair,
        "fair_low": min(applicable),
        "fair_high": max(applicable),
        "margin": margin,
        "verdict": verdict,
    }


def _dividend_growth(quote: dict, assumptions: dict) -> tuple[float | None, str]:
    override = assumptions.get("dividend_growth")
    if override is not None:
        return override, "手填"
    cap = assumptions.get("terminal_growth", 0.03)
    cagr = quote.get("dividend_cagr")
    if cagr is None:
        return cap, "永续增速"
    return min(max(cagr, 0.0), cap), "历史分红增速与永续增速的较低者"


def _fmt_pct(value: float | None) -> str:
    if value is None:
        return "缺失"
    return f"{value * 100:.1f}%"


def _fmt_num(value: float | None) -> str:
    if value is None:
        return "缺失"
    return f"{value:,.0f}"


def _profit_detail(latest: float | None, ago: float | None) -> str:
    if latest is None or ago is None:
        return "年报不足"
    return f"最新 {_fmt_num(latest)} / 三年前 {_fmt_num(ago)}"
