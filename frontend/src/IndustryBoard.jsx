import { useEffect, useState } from "react";

export default function IndustryBoard({ onOpen }) {
  const [tree, setTree] = useState([]);
  const [level1, setLevel1] = useState(null);
  const [level2, setLevel2] = useState(null);
  const [level3, setLevel3] = useState(null);
  const [stocks, setStocks] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    fetch("/api/industries")
      .then(async (response) => {
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "行业分类暂时无法获取");
        if (!cancelled) setTree(data.industries || []);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || "行业分类暂时无法获取");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const first = tree.find((item) => item.code === level1);
  const second = first?.children?.find((item) => item.code === level2);
  const thirds = second?.children || [];

  useEffect(() => {
    const code = level3 || level2;
    if (!code) {
      setStocks(null);
      return undefined;
    }
    let cancelled = false;
    setLoading(true);
    setError("");
    fetch(`/api/industries/stocks?code=${encodeURIComponent(code)}`)
      .then(async (response) => {
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || "行业成份暂时无法获取");
        if (!cancelled) setStocks(data.stocks || []);
      })
      .catch((err) => {
        if (!cancelled) {
          setStocks([]);
          setError(err.message || "行业成份暂时无法获取");
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [level2, level3]);

  return (
    <section className="card filters">
      <h2>按行业筛选</h2>
      <p className="note">先选申万一级行业，再选二级和三级细分。点开公司后计算估值。</p>
      {error ? <p className="banner error">{error}</p> : null}
      {tree.length === 0 && !error ? <p className="note">行业分类加载中</p> : null}
      <FilterRow
        label="一级行业"
        items={tree}
        active={level1}
        onSelect={(code) => {
          setLevel1(code);
          setLevel2(null);
          setLevel3(null);
        }}
      />
      {first ? (
        <FilterRow
          label="二级行业"
          items={first.children || []}
          active={level2}
          onSelect={(code) => {
            setLevel2(code);
            setLevel3(null);
          }}
        />
      ) : null}
      {second && thirds.length ? (
        <FilterRow
          label="三级细分"
          items={thirds}
          active={level3}
          onSelect={(code) => setLevel3(code === level3 ? null : code)}
        />
      ) : null}
      {level1 && !level2 ? <p className="note">选择细分行业后查看公司。</p> : null}
      {loading ? <p className="note">公司列表加载中</p> : null}
      {stocks ? (
        <div className="report-list">
          <table className="stock-table">
            <thead>
              <tr>
                <th>代码</th>
                <th>名称</th>
                <th>现价</th>
                <th>市盈率</th>
                <th>市净率</th>
                <th>股息率</th>
                <th>细分</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {stocks.map((stock) => (
                <tr key={stock.code}>
                  <td>{stock.code}</td>
                  <td>{stock.name}</td>
                  <td>{num(stock.price)}</td>
                  <td>{num(stock.pe)}</td>
                  <td>{num(stock.pb)}</td>
                  <td>{pct(stock.dividend_yield)}</td>
                  <td>{stock.industry_name}</td>
                  <td>
                    <button type="button" className="text-button" onClick={() => onOpen(stock)}>
                      估值
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {stocks.length === 0 && !loading ? <p className="note">这个行业下面没有成份股。</p> : null}
        </div>
      ) : null}
    </section>
  );
}

function FilterRow({ label, items, active, onSelect }) {
  return (
    <div>
      <p className="filter-label">{label}</p>
      <div className="filter-row">
        {items.map((item) => (
          <button
            key={item.code}
            type="button"
            className={item.code === active ? "chip active" : "chip"}
            onClick={() => onSelect(item.code)}
          >
            {item.name}
          </button>
        ))}
      </div>
    </div>
  );
}

function num(value) {
  if (value == null || Number.isNaN(value)) return "—";
  return Number(value).toLocaleString("zh-CN", { maximumFractionDigits: 2 });
}

function pct(value) {
  if (value == null || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(1)}%`;
}
