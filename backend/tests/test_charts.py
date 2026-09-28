from app.data.charts import (
    build_balance_sheet,
    build_market_caps,
    build_pe,
    build_quarter_profits,
    build_revenue,
    build_ttm_profits,
    pe_bands,
)


def test_revenue_keeps_disclosed_total_since_first_report():
    points = build_revenue(
        [
            {"date": "2001-12-31", "revenue": 100},
            {"date": "2002-06-30", "revenue": 80},
            {"date": "2002-03-31", "revenue": None},
        ]
    )
    assert [point["date"] for point in points] == ["2001-12-31", "2002-06-30"]
    assert points[0]["value"] == 100


def test_market_cap_is_unadjusted_price_times_shares_then_in_force():
    caps = build_market_caps(
        [
            {"date": "2001-08-27", "price": 35.55},
            {"date": "2002-01-04", "price": 40},
        ],
        [
            {"date": "2001-08-27", "shares": 1000},
            {"date": "2002-01-01", "shares": 1500},
        ],
    )
    assert caps[0]["value"] == 35.55 * 1000
    assert caps[1]["value"] == 40 * 1500


def test_ttm_profit_uses_four_single_quarters():
    quarters = build_quarter_profits(
        [
            {"date": "2024-03-31", "profit": 10},
            {"date": "2024-06-30", "profit": 30},
            {"date": "2024-09-30", "profit": 60},
            {"date": "2024-12-31", "profit": 100},
            {"date": "2025-03-31", "profit": 15},
        ]
    )
    assert quarters[1] == (quarters[1][0], 20)
    ttm = build_ttm_profits(quarters)
    assert ttm[0]["date"] == "2024-12-31"
    assert ttm[0]["value"] == 100
    assert ttm[1]["value"] == 105


def test_pe_mean_and_one_standard_deviation_bands():
    pe = build_pe(
        [
            {"date": "2024-12-31", "value": 1000},
            {"date": "2025-01-02", "value": 1200},
            {"date": "2025-04-01", "value": 800},
        ],
        [{"date": "2024-12-31", "value": 100}],
    )
    assert [round(point["value"], 2) for point in pe] == [10, 12, 8]
    bands = pe_bands([point["value"] for point in pe])
    assert bands["mean"] == 10
    assert round(bands["high"], 6) == round(bands["mean"] + bands["std"], 6)
    assert round(bands["low"], 6) == round(bands["mean"] - bands["std"], 6)


def test_balance_sheet_groups_match_latest_report_layout():
    yi = 100_000_000
    items = {
        item["name"] + item["side"]: round(item["value"] / yi, 2)
        for item in build_balance_sheet(
            {
                "MONETARYFUNDS": 516.45 * yi,
                "LEND_FUND": 1263.51 * yi,
                "NOTE_ACCOUNTS_RECE": 28.54 * yi,
                "TOTAL_OTHER_RECE": 0.50 * yi,
                "PREPAYMENT": 0.22 * yi,
                "LOAN_ADVANCE": 21.34 * yi,
                "INVENTORY": 549.72 * yi,
                "NONCURRENT_ASSET_1YEAR": 7.18 * yi,
                "OTHER_CURRENT_ASSET": 0.74 * yi,
                "OTHER_NONCURRENT_FINASSET": 40.31 * yi,
                "CREDITOR_INVEST": 10.04 * yi,
                "INVEST_REALESTATE": 0.07 * yi,
                "FIXED_ASSET": 217.58 * yi,
                "CIP": 27.62 * yi,
                "INTANGIBLE_ASSET": 87.17 * yi,
                "DEVELOP_EXPENSE": 1.43 * yi,
                "USERIGHT_ASSET": 2.41 * yi,
                "DEFER_TAX_ASSET": 56.54 * yi,
                "OTHER_NONCURRENT_ASSET": 1.87 * yi,
                "LONG_PREPAID_EXPENSE": 1.42 * yi,
                "NONCURRENT_LIAB_1YEAR": 0.55 * yi,
                "ACCOUNTS_PAYABLE": 29.52 * yi,
                "NOTE_ACCOUNTS_PAYABLE": 29.52 * yi,
                "TOTAL_OTHER_PAYABLE": 63.28 * yi,
                "CONTRACT_LIAB": 55.07 * yi,
                "ACCEPT_DEPOSIT_INTERBANK": 206.34 * yi,
                "STAFF_SALARY_PAYABLE": 4.27 * yi,
                "TAX_PAYABLE": 62.34 * yi,
                "OTHER_CURRENT_LIAB": 7.06 * yi,
                "TOTAL_NONCURRENT_LIAB": 2.79 * yi,
            }
        )
    }
    assert items["现金asset"] == 1779.96
    assert items["应收款asset"] == 29.04
    assert items["预付款asset"] == 21.56
    assert items["存货asset"] == 549.72
    assert items["其它流动asset"] == 7.92
    assert items["长期投资asset"] == 50.42
    assert items["固定资产asset"] == 245.20
    assert items["无形&商誉asset"] == 91.01
    assert items["其它固定asset"] == 59.83
    assert items["短期借款liability"] == 0.55
    assert items["应付款liability"] == 92.80
    assert items["预收款liability"] == 261.41
    assert items["薪酬&税liability"] == 66.61
    assert items["其它流动liability"] == 7.06
    assert items["长期借款liability"] == 0
    assert items["其它非流动liability"] == 2.79
