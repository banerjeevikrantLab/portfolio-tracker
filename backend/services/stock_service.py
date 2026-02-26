import yfinance as yf
from datetime import datetime, timezone


def fetch_stock_data(ticker: str) -> dict:
    """Fetch current price and company name for a single ticker."""
    try:
        t = yf.Ticker(ticker)

        current_price = 0.0
        # Try 1d history first (works during market hours)
        hist = t.history(period="1d")
        if not hist.empty:
            current_price = float(hist["Close"].iloc[-1])

        # Fallback: use daily bars (last close) when intraday is empty (market closed)
        if current_price <= 0:
            hist = t.history(period="5d", interval="1d")
            if not hist.empty:
                current_price = float(hist["Close"].iloc[-1])

        # Fallback: fast_info or info (has regularMarketPrice, previousClose)
        if current_price <= 0:
            try:
                info = t.info
                current_price = float(
                    info.get("regularMarketPrice")
                    or info.get("previousClose")
                    or info.get("currentPrice")
                    or 0
                )
            except Exception:
                pass

        if current_price <= 0 and hasattr(t, "fast_info"):
            try:
                fi = t.fast_info
                if hasattr(fi, "last_price") and fi.last_price:
                    current_price = float(fi.last_price)
                elif hasattr(fi, "previous_close") and fi.previous_close:
                    current_price = float(fi.previous_close)
            except Exception:
                pass

        company_name = ticker.upper()
        try:
            full_info = t.info
            company_name = full_info.get("shortName") or full_info.get("longName") or ticker.upper()
        except Exception:
            pass

        return {
            "current_price": round(current_price, 2),
            "company_name": company_name or ticker.upper(),
        }
    except Exception as e:
        print(f"Error fetching data for {ticker}: {e}")
        return {"current_price": 0.0, "company_name": ticker.upper()}


def fetch_batch_prices(tickers: list[str]) -> dict[str, float]:
    """Fetch current prices for multiple tickers at once."""
    if not tickers:
        return {}

    results = {t: 0.0 for t in tickers}

    def _extract_prices(data, interval_used: str) -> bool:
        """Extract prices from download result. Returns True if any data found."""
        found = False
        if data.empty:
            return False
        try:
            if len(tickers) == 1:
                ticker = tickers[0]
                if "Close" in data.columns and not data["Close"].isna().all():
                    results[ticker] = round(float(data["Close"].dropna().iloc[-1]), 2)
                    found = True
            else:
                for ticker in tickers:
                    try:
                        if ticker in data.columns.get_level_values(0):
                            ticker_data = data[ticker]
                            if not ticker_data.empty and "Close" in ticker_data.columns:
                                close = ticker_data["Close"].dropna()
                                if not close.empty:
                                    results[ticker] = round(float(close.iloc[-1]), 2)
                                    found = True
                    except Exception:
                        pass
        except Exception:
            pass
        return found

    # Try 1m first (live prices during market hours)
    try:
        data = yf.download(
            tickers, period="1d", interval="1m", group_by="ticker", progress=False, threads=False
        )
        if _extract_prices(data, "1m"):
            return results
    except Exception as e:
        print(f"Error in batch price fetch (1m): {e}")

    # Fallback: 1d interval (last close - works when market closed)
    try:
        data = yf.download(
            tickers, period="5d", interval="1d", group_by="ticker", progress=False, threads=False
        )
        _extract_prices(data, "1d")
    except Exception as e:
        print(f"Error in batch price fetch (1d): {e}")

    return results


def is_market_open() -> bool:
    """Check if US stock market is currently open (9:30 AM - 4:00 PM ET, Mon-Fri)."""
    from zoneinfo import ZoneInfo

    now = datetime.now(ZoneInfo("America/New_York"))
    if now.weekday() >= 5:
        return False
    market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
    return market_open <= now <= market_close
