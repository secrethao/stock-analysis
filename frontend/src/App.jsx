import { useEffect, useState } from "react";
import IndustryBoard from "./IndustryBoard.jsx";
import CompanyCharts from "./CompanyCharts.jsx";

const EMPTY_FORM = {
  targetPe: "",
  targetPb: "",
  requiredReturn: "10",
  discountRate: "10",
  terminalGrowth: "3",
  forecastGrowth: "",
  dividendGrowth: "",
  marginThreshold: "25",
  roeThreshold: "10",
};

const VERDICT_CLASS = {
  低估可关注: "good",
  便宜但质量存疑: "warn",
  大致合理: "mid",
  偏贵: "bad",
  证据不足: "muted",
};

export default function App() {
  const [code, setCode] = useState("");
  const [active, setActive] = useState(null);
  const [form, setForm] = useState(EMPTY_FORM);
  const [result, setResult] = useState(null);
  const [reports, setReports] = useState(null);
  const [charts, setCharts] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function valuate(event, target = active) {
    event?.preventDefault();
    const normalized = (target?.code || code).trim();
    if (!/^\d{6}$/.test(normalized)) {
      setError("请输入 6 位 A 股代码");
      setResult(null);
      return;
    }
    const loadReports = !result || result.code !== normalized;
    setLoading(true);
    setError("");
    if (loadReports) {
      setReports(null);
      setCharts(null);
    }
    const reportTask = loadReports ? fetch(`/api/reports/${normalized}`).then((response) => response.json()) : null;
    const chartTask = loadReports ? fetch(`/api/charts/${normalized}`).then((response) => response.json()) : null;
    const industry = target?.industryCode ? `?industry=${encodeURIComponent(target.industryCode)}` : "";
    try {
      const response = await fetch(`/api/valuate/${normalized}${industry}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(toPayload(form)),
      });
      const data = await response.json();
      if (!response.ok) {
        const detail = Array.isArray(data.detail)
          ? data.detail.map((item) => item.msg).join("；")
          : data.detail;
        throw new Error(detail || "估值失败");
      }
      setResult(data);
      if (reportTask) {
        try {
          const reportData = await reportTask;
          setReports(reportData?.reports ? reportData : { reports: [], error: "暂时无法获取财报链接" });
        } catch {
          setReports({ reports: [], error: "暂时无法获取财报链接" });
        }
      }
      if (chartTask) {
        try {
          const chartData = await chartTask;
          setCharts(chartData?.code ? chartData : { revenue: [], market_cap: [], pe: [], balance_sheets: [], error: "暂时无法获取图表" });
        } catch {
          setCharts({ revenue: [], market_cap: [], pe: [], balance_sheets: [], error: "暂时无法获取图表" });
        }
      }
    } catch (err) {
      setResult(null);
      setReports(null);
      setCharts(null);
      setError(err.message || "无法连接估值服务");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!active) return undefined;
    valuate(null, active);
    return undefined;
  }, [active]);

  function openStock(stock) {
    setResult(null);
    setReports(null);
    setCharts(null);
    setCode(stock.code);
    setActive({ code: stock.code, industryCode: stock.industry_code || null });
  }

  function search(event) {
    event.preventDefault();
    const normalized = code.trim();
    if (!/^\d{6}$/.test(normalized)) {
      setError("请输入 6 位 A 股代码");
      return;
    }
    setResult(null);
    setReports(null);
    setCharts(null);
    setActive({ code: normalized, industryCode: null });
  }

  return (
    <div className="page">
      <header className="top">
        <div>
          <p className="eyebrow">A 股 · 个人估值</p>
          <h1>合理股价看板</h1>
        </div>
        <form className="search" onSubmit={search}>
          <input
            value={code}
            inputMode="numeric"
            maxLength={6}
            placeholder="代码"
            aria-label="股票代码"
            onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))}
          />
          <button type="submit" disabled={loading}>
            {loading ? "计算中" : "估值"}
          </button>
        </form>
      </header>

      {error ? <p className="banner error">{error}</p> : null}

      {active ? (
        <button type="button" className="text-button back" onClick={() => setActive(null)}>
          返回筛选
        </button>
      ) : (
        <IndustryBoard onOpen={openStock} />
      )}

      {result && active ? (
        <>
          <section className={`verdict ${VERDICT_CLASS[result.verdict] || "muted"}`}>
            <div>
              <p className="name">
                {result.name} <span>{result.code}</span>
              </p>
              <p className="stamp">
                行情 {result.price_date || "—"} · 年报 {result.report_period || "—"}
                {result.industry?.l1_name ? ` · ${result.industry.l1_name}` : ""}
                {result.industry?.l2_name ? ` / ${result.industry.l2_name}` : ""}
                {result.industry?.l3_name ? ` / ${result.industry.l3_name}` : ""}
              </p>
            </div>
            <p className="badge">{result.verdict}</p>
          </section>

          <section className="metrics">
            <Metric label="现价" value={money(result.price)} />
            <Metric label="合理价" value={money(result.fair_price)} hint="适用模型中位数" />
            <Metric
              label="合理区间"
              value={
                result.fair_low == null
                  ? "—"
                  : `${money(result.fair_low)} – ${money(result.fair_high)}`
              }
            />
            <Metric label="安全边际" value={pct(result.margin)} />
          </section>

          <CompanyCharts data={charts} />

          <Reports data={reports} />

          <section className="grid">
            <article className="card">
              <h2>估值假设</h2>
              <div className="fields">
                <Field label="目标 PE" value={form.targetPe} placeholder="默认近 5 年中位数" onChange={(value) => setForm({ ...form, targetPe: value })} />
                <Field label="目标 PB" value={form.targetPb} placeholder="默认 ROE / 回报率" onChange={(value) => setForm({ ...form, targetPb: value })} />
                <Field label="要求回报率 %" value={form.requiredReturn} onChange={(value) => setForm({ ...form, requiredReturn: value })} />
                <Field label="折现率 %" value={form.discountRate} onChange={(value) => setForm({ ...form, discountRate: value })} />
                <Field label="永续增速 %" value={form.terminalGrowth} onChange={(value) => setForm({ ...form, terminalGrowth: value })} />
                <Field label="预测增速 %" value={form.forecastGrowth} placeholder="默认营收复合增速的一半" onChange={(value) => setForm({ ...form, forecastGrowth: value })} />
                <Field label="分红增速 %" value={form.dividendGrowth} placeholder="默认不超过永续增速" onChange={(value) => setForm({ ...form, dividendGrowth: value })} />
                <Field label="买入边际 %" value={form.marginThreshold} onChange={(value) => setForm({ ...form, marginThreshold: value })} />
                <Field label="ROE 门槛 %" value={form.roeThreshold} onChange={(value) => setForm({ ...form, roeThreshold: value })} />
              </div>
              <button type="button" onClick={valuate} disabled={loading}>
                按新假设重算
              </button>
              <p className="note">
                本次预测增速 {pct(result.assumptions_used.forecast_growth)} · 目标 PE{" "}
                {plain(result.assumptions_used.target_pe)}
              </p>
            </article>

            <article className="card">
              <h2>质量过滤</h2>
              <ul className="checks">
                {result.quality.items.map((item) => (
                  <li key={item.name} className={item.passed ? "pass" : "fail"}>
                    <strong>{item.name}</strong>
                    <span>{item.detail}</span>
                    <em>{item.rule}</em>
                  </li>
                ))}
              </ul>
            </article>
          </section>

          <section className="card">
            <h2>模型明细</h2>
            <table>
              <thead>
                <tr>
                  <th>模型</th>
                  <th>合理价</th>
                  <th>相对现价</th>
                  <th>假设 / 原因</th>
                </tr>
              </thead>
              <tbody>
                {result.models.map((model) => (
                  <tr key={model.name}>
                    <td>{model.name}</td>
                    <td>{model.applicable ? money(model.price) : "不适用"}</td>
                    <td className={premiumClass(model.premium_vs_price)}>
                      {pct(model.premium_vs_price)}
                    </td>
                    <td>{model.applicable ? formatAssumptions(model.assumptions) : model.reason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <p className="note">
              DCF 的净负债按 0 计。自由现金流近似为经营现金流，未扣除资本开支。
            </p>
          </section>

          {result.peers?.length ? (
            <section className="card">
              <h2>同行业类比</h2>
              <p className="note">
                类比价格用申万三级「{result.industry?.l3_name || "同行业"}」可比公司的 PE、PB 中位数，不含本公司。
              </p>
              <div className="report-list">
                <table>
                  <thead>
                    <tr>
                      <th>代码</th>
                      <th>名称</th>
                      <th>现价</th>
                      <th>市盈率</th>
                      <th>市净率</th>
                      <th>股息率</th>
                    </tr>
                  </thead>
                  <tbody>
                    {result.peers.map((peer) => (
                      <tr key={peer.code}>
                        <td>{peer.code}</td>
                        <td>{peer.name}</td>
                        <td>{money(peer.price)}</td>
                        <td>{plain(peer.pe)}</td>
                        <td>{plain(peer.pb)}</td>
                        <td>{pct(peer.dividend_yield)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          ) : null}

          <section className="card">
            <h2>DCF 敏感性</h2>
            <Sensitivity rows={result.sensitivity} />
          </section>
        </>
      ) : (
        active ? <p className="empty">正在计算合理价、安全边际和买入参考。</p> : null
      )}

      <footer>决策辅助，非投资建议。结论随假设变化，请自行核对财务数据。</footer>
    </div>
  );
}

const PERIODS = ["一季报", "半年报", "三季报", "年报"];

function Reports({ data }) {
  const grouped = new Map();
  for (const report of data?.reports || []) {
    if (!grouped.has(report.year)) grouped.set(report.year, new Map());
    grouped.get(report.year).set(report.period, report);
  }
  const years = [...grouped.keys()];
  return (
    <section className="card reports">
      <h2>历史财报</h2>
      <p className="note">年报、半年报、一季报和三季报原文，打开后是对应报告期的公告。</p>
      {data == null ? <p className="note">财报链接加载中</p> : null}
      {data?.error ? <p className="banner error">{data.error}</p> : null}
      {data && !data.error && years.length === 0 ? <p className="note">暂无定期报告链接</p> : null}
      <div className="report-list">
        {years.map((year) => (
          <div className="report-row" key={year}>
            <strong>{year}</strong>
            <div className="report-links">
              {PERIODS.map((period) => {
                const report = grouped.get(year).get(period);
                if (!report) return null;
                return (
                  <a key={period} href={report.url} target="_blank" rel="noreferrer" title={report.title}>
                    {period}
                    <span>{report.date}</span>
                  </a>
                );
              })}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function Metric({ label, value, hint }) {
  return (
    <article className="metric">
      <p>{label}</p>
      <strong>{value}</strong>
      {hint ? <span>{hint}</span> : null}
    </article>
  );
}

function Field({ label, value, onChange, placeholder }) {
  return (
    <label>
      {label}
      <input
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function Sensitivity({ rows }) {
  const discounts = [...new Set(rows.map((row) => row.discount_rate))];
  const terminals = [...new Set(rows.map((row) => row.terminal_growth))];
  return (
    <table>
      <thead>
        <tr>
          <th>折现率 \ 永续增速</th>
          {terminals.map((rate) => (
            <th key={rate}>{pct(rate)}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {discounts.map((discount) => (
          <tr key={discount}>
            <th>{pct(discount)}</th>
            {terminals.map((terminal) => {
              const cell = rows.find(
                (row) => row.discount_rate === discount && row.terminal_growth === terminal,
              );
              return <td key={terminal}>{cell?.applicable ? money(cell.price) : "不适用"}</td>;
            })}
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function toPayload(form) {
  return {
    target_pe: optionalNumber(form.targetPe),
    target_pb: optionalNumber(form.targetPb),
    required_return: Number(form.requiredReturn) / 100,
    discount_rate: Number(form.discountRate) / 100,
    terminal_growth: Number(form.terminalGrowth) / 100,
    forecast_growth: optionalNumber(form.forecastGrowth, true),
    dividend_growth: optionalNumber(form.dividendGrowth, true),
    margin_threshold: Number(form.marginThreshold) / 100,
    roe_threshold: Number(form.roeThreshold) / 100,
  };
}

function optionalNumber(raw, asPercent = false) {
  if (raw === "" || raw == null) return null;
  const value = Number(raw);
  if (Number.isNaN(value)) return null;
  return asPercent ? value / 100 : value;
}

function money(value) {
  if (value == null || Number.isNaN(value)) return "—";
  return value.toLocaleString("zh-CN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function pct(value) {
  if (value == null || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(1)}%`;
}

function plain(value) {
  if (value == null || Number.isNaN(value)) return "—";
  return Number(value).toFixed(2);
}

function premiumClass(value) {
  if (value == null) return "";
  return value >= 0 ? "up" : "down";
}

function formatAssumptions(assumptions) {
  const skip = new Set(["说明", "股权价值", "第5年自由现金流", "总股本"]);
  return Object.entries(assumptions)
    .filter(([key]) => !skip.has(key))
    .map(([key, value]) => `${key} ${formatAssumption(key, value)}`)
    .join(" · ");
}

function formatAssumption(key, value) {
  if (typeof value === "string") return value;
  if (value == null || Number.isNaN(value)) return "—";
  if (["近三年平均ROE", "要求回报率", "预测增速", "折现率", "永续增速", "分红增速"].includes(key)) {
    return pct(value);
  }
  if (Math.abs(value) >= 1000) return money(value);
  return Number(value).toFixed(2);
}
