from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from app.data.fetcher import QuoteError, get_quote
from app.data.industry import attach_peers, get_industry_tree, list_industry_stocks
from app.data.charts import get_charts
from app.data.reports import get_reports
from app.data.trend import get_trend
from app.schemas import Assumptions
from app.valuation.aggregate import valuate

app = FastAPI(title="A股估值看板")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:5173", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/quote/{code}")
def quote(code: str):
    try:
        return get_quote(code)
    except QuoteError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/industries")
def industries():
    try:
        tree = get_industry_tree()
    except QuoteError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="行业分类暂时无法获取") from exc
    return {"industries": tree["industries"]}


@app.get("/api/industries/stocks")
def industry_stocks(code: str = Query(min_length=1)):
    try:
        return list_industry_stocks(code)
    except QuoteError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="行业成份暂时无法获取") from exc


@app.get("/api/charts/{code}")
def charts(code: str):
    try:
        return get_charts(code)
    except QuoteError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/trend/{code}")
def trend(code: str):
    try:
        return get_trend(code)
    except QuoteError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.get("/api/reports/{code}")
def reports(code: str):
    try:
        return get_reports(code)
    except QuoteError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@app.post("/api/valuate/{code}")
def valuate_code(
    code: str,
    body: Assumptions | None = None,
    industry: str | None = None,
):
    assumptions = body or Assumptions()
    try:
        snapshot = attach_peers(get_quote(code), industry)
    except QuoteError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return valuate(snapshot, assumptions.model_dump())
