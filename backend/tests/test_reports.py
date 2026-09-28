from app.data.reports import dedupe_reports, parse_notice


def _item(column_name: str, title: str, art_code: str, notice_date: str) -> dict:
    return {
        "columns": [{"column_name": column_name}],
        "title": title,
        "art_code": art_code,
        "notice_date": notice_date,
    }


def test_parse_keeps_quarterly_and_annual_full_reports():
    annual = parse_notice("600519", _item("年度报告全文", "贵州茅台2025年年度报告", "a1", "2026-04-17"))
    first = parse_notice("600519", _item("一季度报告全文", "贵州茅台2026年第一季度报告", "q1", "2026-04-25"))
    half = parse_notice("600519", _item("半年度报告全文", "贵州茅台2026年半年度报告", "h1", "2026-08-15"))
    third = parse_notice("600519", _item("三季度报告全文", "贵州茅台2025年第三季度报告", "q3", "2025-10-30"))
    assert [annual["period"], first["period"], half["period"], third["period"]] == [
        "年报",
        "一季报",
        "半年报",
        "三季报",
    ]
    assert annual["year"] == 2025
    assert annual["url"].endswith("/600519/a1.html")


def test_parse_drops_summaries_and_dividend_notices():
    assert parse_notice("600519", _item("年度报告摘要", "贵州茅台2025年年度报告摘要", "s", "2026-04-17")) is None
    assert parse_notice("600519", _item("分配方案实施", "贵州茅台2025年度利润分配实施公告", "d", "2026-06-22")) is None


def test_dedupe_keeps_latest_link_and_sorts_by_period():
    reports = dedupe_reports(
        [
            parse_notice("600519", _item("年度报告全文", "甲2024年年度报告", "old", "2025-04-01")),
            parse_notice("600519", _item("年度报告全文", "甲2024年年度报告", "new", "2025-04-18")),
            parse_notice("600519", _item("三季度报告全文", "甲2025年第三季度报告", "q3", "2025-10-30")),
            parse_notice("600519", _item("一季度报告全文", "甲2025年第一季度报告", "q1", "2025-04-30")),
            parse_notice("600519", _item("半年度报告全文", "甲2025年半年度报告", "h", "2025-08-13")),
            parse_notice("600519", _item("年度报告全文", "甲2025年年度报告", "y", "2026-04-03")),
        ]
    )
    assert [(item["year"], item["period"]) for item in reports] == [
        (2025, "一季报"),
        (2025, "半年报"),
        (2025, "三季报"),
        (2025, "年报"),
        (2024, "年报"),
    ]
    annual_2024 = next(item for item in reports if item["year"] == 2024)
    assert annual_2024["url"].endswith("/new.html")
