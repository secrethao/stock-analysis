import { useEffect, useState } from "react";

export default function CompanyCharts({ data }) {
  const sheets = data?.balance_sheets || [];
  const [periodIndex, setPeriodIndex] = useState(0);
  useEffect(() => {
    setPeriodIndex(0);
  }, [data?.code]);
  const selected = sheets[Math.min(periodIndex, Math.max(sheets.length - 1, 0))] || null;
  const name = data?.name || "公司";

  return (
    <>
      <section className="card">
        <h2>公司市值与业绩增长趋势</h2>
        <p className="chart-heading">{name}市值与业绩增长趋势</p>
        <p className="note">柱为各报告期披露的营业总收入，季报和半年报是年初至报告期末的累计数。折线为不复权收盘价乘以当时总股本。</p>
        {data == null ? <p className="note">图表加载中</p> : null}
        {data?.error ? <p className="banner error">{data.error}</p> : null}
        {data?.revenue?.length || data?.market_cap?.length ? (
          <MarketChart revenue={data.revenue || []} marketCap={data.market_cap || []} />
        ) : null}
      </section>

      <section className="card">
        <h2>市盈率</h2>
        <p className="chart-heading">{name}市盈率趋势</p>
        <p className="note">市盈率等于总市值除以近四个季度归母净利润。均值和高低估线按上市以来的正市盈率计算，高估线为均值加一个标准差，低估线为均值减一个标准差。</p>
        {data?.pe?.length ? (
          <PeChart
            points={data.pe}
            mean={data.pe_mean}
            high={data.pe_high}
            low={data.pe_low}
          />
        ) : data ? (
          <p className="note">暂时无法计算上市以来的市盈率</p>
        ) : null}
      </section>

      <section className="card">
        <div className="chart-toolbar">
          <h2>资产负债表</h2>
          <div className="period-nav">
            <button type="button" className="text-button" onClick={() => setPeriodIndex(0)} disabled={!sheets.length || periodIndex === 0}>
              当期数据
            </button>
            <button
              type="button"
              className="text-button"
              onClick={() => setPeriodIndex((index) => Math.min(index + 1, sheets.length - 1))}
              disabled={periodIndex >= sheets.length - 1}
            >
              上一期
            </button>
            <button
              type="button"
              className="text-button"
              onClick={() => setPeriodIndex((index) => Math.max(index - 1, 0))}
              disabled={periodIndex <= 0}
            >
              下一期
            </button>
          </div>
        </div>
        <p className="chart-heading">
          {name}资产负债表
          {selected ? <span>{selected.date}</span> : null}
        </p>
        <p className="note">单位为亿元，取自该报告期资产负债表。蓝色为资产科目，红色为负债科目。</p>
        {data?.balance_error ? <p className="banner error">{data.balance_error}</p> : null}
        {selected ? <BalanceChart items={selected.items || []} /> : data ? <p className="note">暂时没有资产负债表数据</p> : null}
      </section>
    </>
  );
}

function MarketChart({ revenue, marketCap }) {
  const width = 860;
  const height = 360;
  const pad = { top: 28, right: 64, bottom: 58, left: 64 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;
  const times = [...revenue, ...marketCap].map((point) => Date.parse(point.date));
  const minT = Math.min(...times);
  const maxT = Math.max(...times);
  const span = Math.max(maxT - minT, 1);
  const maxRevenue = Math.max(...revenue.map((point) => point.value), 1);
  const maxCap = Math.max(...marketCap.map((point) => point.value), 1);
  const x = (value) => pad.left + ((Date.parse(value) - minT) / span) * plotW;
  const yRevenue = (value) => pad.top + plotH - (value / maxRevenue) * plotH;
  const yCap = (value) => pad.top + plotH - (value / maxCap) * plotH;
  const barW = Math.max(2, Math.min(14, (plotW / Math.max(revenue.length, 1)) * 0.55));
  const line = marketCap.map((point) => `${x(point.date)},${yCap(point.value)}`).join(" ");

  return (
    <svg className="trend-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="上市以来总营收柱状图和总市值折线图">
      <text x={pad.left} y="16" className="axis">总营收</text>
      <text x={width - pad.right} y="16" textAnchor="end" className="axis">总市值</text>
      {[0, 0.5, 1].map((ratio) => {
        const y = pad.top + plotH * (1 - ratio);
        return (
          <g key={ratio}>
            <line x1={pad.left} x2={width - pad.right} y1={y} y2={y} stroke="#e4dcd0" />
            <text x={pad.left - 8} y={y + 4} textAnchor="end" className="axis">{yi(maxRevenue * ratio)}</text>
            <text x={width - pad.right + 8} y={y + 4} className="axis">{yi(maxCap * ratio)}</text>
          </g>
        );
      })}
      {revenue.map((point) => (
        <rect
          key={point.date}
          x={x(point.date) - barW / 2}
          y={yRevenue(point.value)}
          width={barW}
          height={Math.max(plotH - (yRevenue(point.value) - pad.top), 0)}
          fill="#3b82f6"
        >
          <title>{`${point.date} 总营收 ${yi(point.value)}亿`}</title>
        </rect>
      ))}
      {line ? <polyline points={line} fill="none" stroke="#e11d48" strokeWidth="1.6" /> : null}
      {timeTicks(minT, maxT).map((tick) => (
        <text key={tick} x={x(new Date(tick).toISOString().slice(0, 10))} y={pad.top + plotH + 18} textAnchor="middle" className="axis">
          {new Date(tick).toISOString().slice(0, 10)}
        </text>
      ))}
      <g transform={`translate(${width / 2 - 70},${height - 8})`}>
        <rect width="12" height="8" y="-8" fill="#3b82f6" />
        <text x="16" className="axis">总营收</text>
        <line x1="78" x2="98" y1="-4" y2="-4" stroke="#e11d48" strokeWidth="2" />
        <text x="102" className="axis">总市值</text>
      </g>
    </svg>
  );
}

function PeChart({ points, mean, high, low }) {
  const width = 860;
  const height = 360;
  const pad = { top: 20, right: 72, bottom: 58, left: 48 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;
  const times = points.map((point) => Date.parse(point.date));
  const minT = Math.min(...times);
  const maxT = Math.max(...times);
  const span = Math.max(maxT - minT, 1);
  const levels = [0, ...points.map((point) => point.value), mean, high, low].filter((value) => value != null);
  const maxPe = Math.max(...levels, 1) * 1.08;
  const minPe = Math.min(0, ...levels);
  const x = (value) => pad.left + ((Date.parse(value) - minT) / span) * plotW;
  const y = (value) => pad.top + ((maxPe - value) / (maxPe - minPe)) * plotH;
  const line = points.map((point) => `${x(point.date)},${y(point.value)}`).join(" ");
  const guides = [
    { value: mean, color: "#d4a017", label: "均值" },
    { value: low, color: "#1f9d55", label: "低估线" },
    { value: high, color: "#d23b3b", label: "高估线" },
  ];

  return (
    <svg className="trend-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="上市以来市盈率、均值、高估线和低估线">
      {[0, 0.25, 0.5, 0.75, 1].map((ratio) => {
        const value = minPe + (maxPe - minPe) * ratio;
        const yPos = y(value);
        return (
          <g key={ratio}>
            <line x1={pad.left} x2={width - pad.right} y1={yPos} y2={yPos} stroke="#e4dcd0" />
            <text x={pad.left - 8} y={yPos + 4} textAnchor="end" className="axis">{value.toFixed(0)}</text>
          </g>
        );
      })}
      {guides.map((guide) =>
        guide.value == null ? null : (
          <g key={guide.label}>
            <line
              x1={pad.left}
              x2={width - pad.right}
              y1={y(guide.value)}
              y2={y(guide.value)}
              stroke={guide.color}
              strokeDasharray="5 4"
            />
            <text x={width - pad.right + 6} y={y(guide.value) + 4} className="axis" fill={guide.color}>
              {guide.value.toFixed(2)}
            </text>
          </g>
        ),
      )}
      <polyline points={line} fill="none" stroke="#2563eb" strokeWidth="1.6" />
      {timeTicks(minT, maxT).map((tick) => (
        <text key={tick} x={pad.left + ((tick - minT) / span) * plotW} y={pad.top + plotH + 18} textAnchor="middle" className="axis">
          {new Date(tick).toISOString().slice(0, 10)}
        </text>
      ))}
      <g transform={`translate(${width / 2 - 150},${height - 8})`}>
        <line x1="0" x2="18" y1="-4" y2="-4" stroke="#2563eb" strokeWidth="2" />
        <text x="22" className="axis">公司市盈率</text>
        <line x1="92" x2="110" y1="-4" y2="-4" stroke="#d4a017" strokeDasharray="4 3" />
        <text x="114" className="axis">均值</text>
        <line x1="150" x2="168" y1="-4" y2="-4" stroke="#1f9d55" strokeDasharray="4 3" />
        <text x="172" className="axis">低估线</text>
        <line x1="214" x2="232" y1="-4" y2="-4" stroke="#d23b3b" strokeDasharray="4 3" />
        <text x="236" className="axis">高估线</text>
      </g>
    </svg>
  );
}

function BalanceChart({ items }) {
  const width = 980;
  const height = 420;
  const pad = { top: 28, right: 16, bottom: 72, left: 48 };
  const plotW = width - pad.left - pad.right;
  const plotH = height - pad.top - pad.bottom;
  const maxValue = Math.max(...items.map((item) => item.value || 0), 1);
  const step = plotW / items.length;
  const barW = Math.min(28, step * 0.62);
  const y = (value) => pad.top + plotH - (value / maxValue) * plotH;

  return (
    <svg className="trend-chart" viewBox={`0 0 ${width} ${height}`} role="img" aria-label="最近报告期资产负债表">
      {[0, 0.5, 1].map((ratio) => {
        const yPos = pad.top + plotH * (1 - ratio);
        return (
          <g key={ratio}>
            <line x1={pad.left} x2={width - pad.right} y1={yPos} y2={yPos} stroke="#e4dcd0" />
            <text x={pad.left - 8} y={yPos + 4} textAnchor="end" className="axis">{yi(maxValue * ratio)}</text>
          </g>
        );
      })}
      {items.map((item, index) => {
        const cx = pad.left + step * index + step / 2;
        const top = y(item.value || 0);
        return (
          <g key={`${item.side}-${item.name}-${index}`}>
            <rect
              x={cx - barW / 2}
              y={top}
              width={barW}
              height={Math.max(pad.top + plotH - top, 0)}
              fill={item.side === "asset" ? "#3b82f6" : "#e11d48"}
            >
              <title>{`${item.name} ${yi(item.value)}亿`}</title>
            </rect>
            <text x={cx} y={top - 4} textAnchor="middle" className="axis">{yi(item.value, 2)}</text>
            <text transform={`translate(${cx},${pad.top + plotH + 14}) rotate(40)`} className="axis">{item.name}</text>
          </g>
        );
      })}
    </svg>
  );
}

function timeTicks(minT, maxT) {
  const count = 6;
  return Array.from({ length: count }, (_, index) => minT + ((maxT - minT) * index) / (count - 1));
}

function yi(value, digits = 0) {
  const amount = (value || 0) / 1e8;
  return amount.toLocaleString("zh-CN", { maximumFractionDigits: digits, minimumFractionDigits: digits });
}
