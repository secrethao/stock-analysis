from datetime import date

from app.data.trend import build_trend


def test_annual_revenue_bars_and_market_cap_on_each_report():
    points = build_trend(
        [
            {"date": "2024-03-31", "revenue": 100},
            {"date": "2024-06-30", "revenue": 220},
            {"date": "2024-09-30", "revenue": 340},
            {"date": "2024-12-31", "revenue": 500},
            {"date": "2025-03-31", "revenue": 120},
        ],
        [
            {"date": "2024-03-29", "market_cap": 1000},
            {"date": "2024-06-28", "market_cap": 1100},
            {"date": "2024-09-30", "market_cap": 900},
            {"date": "2024-12-31", "market_cap": 1300},
            {"date": "2025-03-31", "market_cap": 1400},
        ],
        today=date(2026, 9, 24),
    )
    by_label = {point["label"]: point for point in points}
    assert by_label["2024一季报"]["revenue"] is None
    assert by_label["2024一季报"]["market_cap"] == 1000
    assert by_label["2024半年报"]["market_cap"] == 1100
    assert by_label["2024三季报"]["market_cap"] == 900
    assert by_label["2024年报"]["revenue"] == 500
    assert by_label["2024年报"]["market_cap"] == 1300
    assert by_label["2025一季报"]["revenue"] is None
    assert by_label["2025一季报"]["market_cap"] == 1400


def test_market_cap_uses_last_close_on_or_before_report_date():
    points = build_trend(
        [{"date": "2025-12-31", "revenue": 80}],
        [
            {"date": "2025-12-30", "market_cap": 10},
            {"date": "2025-12-31", "market_cap": 11},
            {"date": "2026-01-02", "market_cap": 12},
        ],
        today=date(2026, 9, 24),
    )
    annual = next(point for point in points if point["label"] == "2025年报")
    assert annual["market_cap"] == 11
    assert annual["revenue"] == 80
