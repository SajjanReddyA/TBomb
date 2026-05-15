from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from flask import Flask, jsonify, render_template, request
import yfinance as yf

app = Flask(__name__)

DEFAULT_SYMBOL = "AAPL"
WATCHLIST = ["AAPL", "MSFT", "GOOGL", "AMZN", "META", "TSLA", "NVDA"]
MARKET_INDEXES = {
    "S&P 500": "^GSPC",
    "NASDAQ": "^IXIC",
    "DOW JONES": "^DJI",
    "RUSSELL 2000": "^RUT",
    "VIX": "^VIX",
}


def _safe(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "item"):
        try:
            return value.item()
        except (TypeError, ValueError):
            return str(value)
    return value


def _records(df) -> List[Dict[str, Any]]:
    if df is None or df.empty:
        return []

    rows: List[Dict[str, Any]] = []
    for index, row in df.iterrows():
        point: Dict[str, Any] = {
            "date": index.strftime("%Y-%m-%d %H:%M") if hasattr(index, "strftime") else str(index)
        }
        for col in df.columns:
            point[col.lower()] = _safe(row[col])
        rows.append(point)
    return rows


def _ticker_info(symbol: str) -> Dict[str, Any]:
    try:
        return yf.Ticker(symbol).info or {}
    except Exception:
        return {}


def _quote_snapshot(symbol: str) -> Dict[str, Any]:
    info = _ticker_info(symbol)
    return {
        "symbol": symbol,
        "name": info.get("shortName") or info.get("longName") or symbol,
        "price": info.get("currentPrice"),
        "change": info.get("regularMarketChange"),
        "change_percent": info.get("regularMarketChangePercent"),
        "volume": info.get("volume"),
        "market_cap": info.get("marketCap"),
    }


@app.route("/")
def home():
    return render_template("index.html", default_symbol=DEFAULT_SYMBOL)


@app.route("/api/stock")
def stock_data():
    symbol = request.args.get("symbol", DEFAULT_SYMBOL).upper().strip()
    if not symbol:
        return jsonify({"error": "symbol is required"}), 400

    ticker = yf.Ticker(symbol)

    try:
        info = ticker.info or {}
    except Exception as err:
        return jsonify({"error": f"Unable to fetch stock info for {symbol}: {err}"}), 502

    history = ticker.history(period="1y", interval="1d")
    intraday = ticker.history(period="1d", interval="5m")

    dividends_df = ticker.dividends.reset_index() if not ticker.dividends.empty else None
    if dividends_df is not None:
        dividends_df = dividends_df.rename(columns={"Dividends": "dividends"})

    actions = _records(ticker.actions)

    payload: Dict[str, Any] = {
        "symbol": symbol,
        "company": {
            "name": info.get("longName"),
            "sector": info.get("sector"),
            "industry": info.get("industry"),
            "website": info.get("website"),
            "country": info.get("country"),
            "employees": info.get("fullTimeEmployees"),
            "description": info.get("longBusinessSummary"),
        },
        "price": {
            "current": info.get("currentPrice"),
            "open": info.get("open"),
            "high": info.get("dayHigh"),
            "low": info.get("dayLow"),
            "previous_close": info.get("previousClose"),
            "volume": info.get("volume"),
            "avg_volume": info.get("averageVolume"),
            "market_cap": info.get("marketCap"),
            "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
            "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
        },
        "valuation": {
            "pe_ratio": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "price_to_book": info.get("priceToBook"),
            "peg_ratio": info.get("pegRatio"),
            "eps": info.get("trailingEps"),
            "forward_eps": info.get("forwardEps"),
            "beta": info.get("beta"),
        },
        "financials": {
            "revenue": info.get("totalRevenue"),
            "gross_profit": info.get("grossProfits"),
            "ebitda": info.get("ebitda"),
            "net_income": info.get("netIncomeToCommon"),
            "operating_cashflow": info.get("operatingCashflow"),
            "free_cashflow": info.get("freeCashflow"),
            "debt_to_equity": info.get("debtToEquity"),
            "profit_margin": info.get("profitMargins"),
            "return_on_assets": info.get("returnOnAssets"),
            "return_on_equity": info.get("returnOnEquity"),
        },
        "events": {
            "earnings_date": str(info.get("earningsDate")),
            "ex_dividend_date": info.get("exDividendDate"),
            "dividend_rate": info.get("dividendRate"),
            "dividend_yield": info.get("dividendYield"),
            "target_mean_price": info.get("targetMeanPrice"),
            "recommendation": info.get("recommendationKey"),
        },
        "history_1y": _records(history[["Open", "High", "Low", "Close", "Volume"]] if not history.empty else history),
        "intraday_5m": _records(intraday[["Open", "High", "Low", "Close", "Volume"]] if not intraday.empty else intraday),
        "dividends": _records(dividends_df),
        "actions": actions,
        "updated_at": datetime.utcnow().isoformat() + "Z",
    }
    return jsonify(payload)


@app.route("/api/market-overview")
def market_overview():
    index_data = [_quote_snapshot(symbol) | {"label": label} for label, symbol in MARKET_INDEXES.items()]
    watchlist_data = [_quote_snapshot(symbol) for symbol in WATCHLIST]

    return jsonify(
        {
            "indexes": index_data,
            "watchlist": watchlist_data,
            "updated_at": datetime.utcnow().isoformat() + "Z",
        }
    )


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
