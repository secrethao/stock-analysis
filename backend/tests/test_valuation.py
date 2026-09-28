import statistics

from app.data.dividends import summarize_dividend_frame
from app.data.industry import peer_stats
from app.valuation.aggregate import quality_checks, valuate
from app.valuation.comps import value_comps
from app.valuation.ddm import value_ddm
from app.valuation.nav import value_nav
import pandas as pd
from app.valuation.dcf import default_forecast_growth, value_dcf
from app.valuation.pb import value_pb
from app.valuation.pe import value_pe


def test_pe_price():
    result = value_pe(10, 20)
    assert result.applicable
    assert result.price == 200


def test_pe_rejects_non_positive_eps():
    result = value_pe(0, 20)
    assert not result.applicable
    assert result.reason == "每股收益不为正"


def test_pe_rejects_missing_target():
    result = value_pe(5, None)
    assert not result.applicable
    assert "历史市盈率" in result.reason


def test_pb_derives_target_from_roe():
    result = value_pb(bps=20, roe_3y=0.2, required_return=0.1, target_pb=None)
    assert result.applicable
    assert result.assumptions["目标PB"] == 2
    assert result.price == 40


def test_pb_rejects_non_positive_book():
    result = value_pb(bps=-1, roe_3y=0.2, required_return=0.1, target_pb=1.5)
    assert not result.applicable
    assert result.reason == "净资产不为正"


def test_pb_rejects_non_positive_roe_when_target_missing():
    result = value_pb(bps=10, roe_3y=-0.01, required_return=0.1, target_pb=None)
    assert not result.applicable


def test_dcf_price_and_net_debt_zero():
    result = value_dcf(
        fcf0=100,
        growth=0.0,
        discount=0.1,
        terminal_growth=0.0,
        shares=10,
        net_debt=0,
        years=5,
    )
    assert result.applicable
    assert result.assumptions["净负债"] == 0
    assert result.price > 0


def test_dcf_rejects_non_positive_cashflow():
    result = value_dcf(0, 0.05, 0.1, 0.03, 1_000)
    assert not result.applicable
    assert result.reason == "经营现金流不为正"


def test_dcf_rejects_discount_not_above_terminal():
    result = value_dcf(100, 0.05, 0.03, 0.03, 100)
    assert not result.applicable
    assert result.reason == "折现率不高于永续增速"


def test_default_growth_is_half_cagr_capped():
    assert default_forecast_growth(0.4) == 0.15
    assert default_forecast_growth(-0.1) == 0.0
    assert default_forecast_growth(0.1) == 0.05
    assert default_forecast_growth(None) is None


def _quote(**overrides):
    base = {
        "code": "600519",
        "name": "贵州茅台",
        "price": 100,
        "price_date": "2026-09-23",
        "report_period": "2025-12-31",
        "shares": 100,
        "eps": 10,
        "bps": 50,
        "pe_median_5y": 20,
        "roe_3y": 0.2,
        "debt_ratio": 0.2,
        "operating_cashflow": 500,
        "net_profit_latest": 300,
        "net_profit_3y_ago": 200,
        "revenue_cagr_3y": 0.1,
    }
    base.update(overrides)
    return base


def test_median_and_undervalued_when_quality_passes():
    result = valuate(_quote(price=50), {"margin_threshold": 0.25, "roe_threshold": 0.10})
    prices = [item["price"] for item in result["models"] if item["applicable"]]
    assert len(prices) >= 2
    assert result["fair_price"] == float(statistics.median(prices))
    assert result["fair_low"] == min(prices)
    assert result["fair_high"] == max(prices)
    assert result["margin"] >= 0.25
    assert result["quality"]["passed"]
    assert result["verdict"] == "低估可关注"


def test_cheap_but_quality_fails():
    result = valuate(
        _quote(price=50, debt_ratio=0.9),
        {"margin_threshold": 0.25},
    )
    assert result["verdict"] == "便宜但质量存疑"
    assert not result["quality"]["passed"]


def test_insufficient_evidence_when_only_one_model():
    result = valuate(
        _quote(eps=-1, bps=-1, operating_cashflow=-1),
        {},
    )
    assert result["verdict"] == "证据不足"
    assert result["fair_price"] is None
    assert result["margin"] is None


def test_overvalued_and_fair_bands():
    expensive = valuate(_quote(price=10_000), {"margin_threshold": 0.25})
    assert expensive["verdict"] == "偏贵"
    fair = valuate(_quote(price=expensive["fair_price"] * 0.9), {"margin_threshold": 0.25})
    assert fair["verdict"] == "大致合理"


def test_quality_fails_when_annual_history_missing():
    quality = quality_checks(0.2, 0.2, 100, 100, None)
    profit = next(item for item in quality["items"] if item["name"] == "利润趋势")
    assert not profit["passed"]
    assert not quality["passed"]


def test_ddm_gordon_price():
    result = value_ddm(2, 0.03, 0.10, "手填")
    assert result.applicable
    assert round(result.price, 2) == round(2 * 1.03 / 0.07, 2)


def test_ddm_rejects_missing_dividend():
    result = value_ddm(0, 0.03, 0.10, "永续增速")
    assert not result.applicable
    assert result.reason == "没有现金分红"


def test_nav_uses_book_value():
    result = value_nav(48)
    assert result.applicable
    assert result.price == 48


def test_comps_uses_peer_multiples():
    result = value_comps(10, 20, peer_pe=15, peer_pb=2, peer_count=5, industry_name="白酒")
    assert result.applicable
    assert result.price == 95


def test_comps_needs_three_peers():
    result = value_comps(10, 20, 15, 2, 2, "白酒")
    assert not result.applicable


def test_dividend_summary_sums_implemented_cash():
    frame = pd.DataFrame(
        [
            {"报告期": "2022-12-31", "现金分红-现金分红比例": 10, "方案进度": "实施方案"},
            {"报告期": "2025-06-30", "现金分红-现金分红比例": 5, "方案进度": "实施方案"},
            {"报告期": "2025-12-31", "现金分红-现金分红比例": 15, "方案进度": "实施方案"},
            {"报告期": "2025-12-31", "现金分红-现金分红比例": 20, "方案进度": "预案"},
        ]
    )
    dps, cagr = summarize_dividend_frame(frame)
    assert dps == 2
    assert cagr == (2 / 1) ** (1 / 3) - 1


def test_peer_median_excludes_self():
    peers = [
        {"code": "000001", "pe": 10, "pb": 1, "market_cap": 1},
        {"code": "000002", "pe": 20, "pb": 2, "market_cap": 3},
        {"code": "000003", "pe": 30, "pb": 3, "market_cap": 2},
        {"code": "000004", "pe": 40, "pb": 4, "market_cap": 4},
    ]
    stats = peer_stats(peers, "000001")
    assert stats["peer_count"] == 3
    assert stats["peer_pe_median"] == 30
    assert stats["peer_pb_median"] == 3


def test_sensitivity_marks_invalid_cells():
    result = valuate(_quote(), {"forecast_growth": 0.05})
    cells = {(row["discount_rate"], row["terminal_growth"]): row for row in result["sensitivity"]}
    assert cells[(0.08, 0.02)]["applicable"]
    assert cells[(0.08, 0.02)]["price"] > 0
    assert len(result["sensitivity"]) == 9
