import yfinance as yf
from datetime import datetime, timezone

# Use curl_cffi to bypass Yahoo's TLS fingerprinting / bot protection
def _get_session():
    try:
        from curl_cffi import requests
        return requests.Session(impersonate="chrome", timeout=10)
    except ImportError:
        return None


def _extract_dividend_info(info: dict) -> dict:
    """Extract dividend data from yfinance info dict, handling both stocks and ETFs.

    Stocks use dividendRate/dividendYield; ETFs use trailingAnnualDividendRate/
    trailingAnnualDividendYield or yield.
    """
    annual_div = float(info.get("dividendRate") or info.get("trailingAnnualDividendRate") or 0)

    # dividendYield is already a percentage (e.g. 4.25 = 4.25%)
    # trailingAnnualDividendYield and yield are decimals (e.g. 0.0425 = 4.25%)
    div_yield = 0.0
    if info.get("dividendYield"):
        div_yield = round(float(info["dividendYield"]), 2)
    elif info.get("trailingAnnualDividendYield"):
        div_yield = round(float(info["trailingAnnualDividendYield"]) * 100, 2)
    elif info.get("yield"):
        div_yield = round(float(info["yield"]) * 100, 2)

    return {
        "annual_dividend": round(annual_div, 2),
        "dividend_yield": div_yield,
    }


def fetch_stock_data(ticker: str) -> dict:
    """Fetch current price, previous close, dividends, 52-week range, and company name."""
    result = {
        "current_price": 0.0,
        "previous_close": 0.0,
        "dividend_yield": 0.0,
        "annual_dividend": 0.0,
        "week52_high": 0.0,
        "week52_low": 0.0,
        "company_name": ticker.upper(),
    }
    try:
        session = _get_session()
        t = yf.Ticker(ticker, session=session)

        current_price = 0.0
        hist = t.history(period="1d")
        if not hist.empty:
            current_price = float(hist["Close"].iloc[-1])

        if current_price <= 0:
            hist = t.history(period="5d", interval="1d")
            if not hist.empty:
                current_price = float(hist["Close"].iloc[-1])

        info = {}
        try:
            info = t.info or {}
        except Exception:
            pass

        if current_price <= 0:
            current_price = float(
                info.get("regularMarketPrice")
                or info.get("previousClose")
                or info.get("currentPrice")
                or 0
            )

        if current_price <= 0 and hasattr(t, "fast_info"):
            try:
                fi = t.fast_info
                if hasattr(fi, "last_price") and fi.last_price:
                    current_price = float(fi.last_price)
                elif hasattr(fi, "previous_close") and fi.previous_close:
                    current_price = float(fi.previous_close)
            except Exception:
                pass

        result["current_price"] = round(current_price, 2)
        result["company_name"] = info.get("shortName") or info.get("longName") or ticker.upper()
        result["previous_close"] = round(float(info.get("previousClose") or info.get("regularMarketPreviousClose") or 0), 2)
        div_info = _extract_dividend_info(info)
        result["dividend_yield"] = div_info["dividend_yield"]
        result["annual_dividend"] = div_info["annual_dividend"]
        result["week52_high"] = round(float(info.get("fiftyTwoWeekHigh") or 0), 2)
        result["week52_low"] = round(float(info.get("fiftyTwoWeekLow") or 0), 2)
    except Exception as e:
        print(f"Error fetching data for {ticker}: {e}")
    return result


def fetch_batch_prices(tickers: list[str]) -> dict[str, float]:
    """Fetch current prices for multiple tickers at once."""
    if not tickers:
        return {}

    session = _get_session()
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
            tickers, period="1d", interval="1m", group_by="ticker", progress=False, threads=False,
            session=session
        )
        if _extract_prices(data, "1m"):
            return results
    except Exception as e:
        print(f"Error in batch price fetch (1m): {e}")

    # Fallback: 1d interval (last close - works when market closed)
    try:
        data = yf.download(
            tickers, period="5d", interval="1d", group_by="ticker", progress=False, threads=False,
            session=session
        )
        _extract_prices(data, "1d")
    except Exception as e:
        print(f"Error in batch price fetch (1d): {e}")

    return results


def fetch_batch_extended_info(tickers: list[str]) -> dict[str, dict]:
    """Fetch previous_close, dividends, and 52-week range for multiple tickers."""
    if not tickers:
        return {}
    session = _get_session()
    results = {}
    for ticker in tickers:
        entry = {"previous_close": 0.0, "dividend_yield": 0.0, "annual_dividend": 0.0,
                 "week52_high": 0.0, "week52_low": 0.0}
        try:
            t = yf.Ticker(ticker, session=session)
            info = t.info or {}
            entry["previous_close"] = round(float(info.get("previousClose") or info.get("regularMarketPreviousClose") or 0), 2)
            div_info = _extract_dividend_info(info)
            entry["dividend_yield"] = div_info["dividend_yield"]
            entry["annual_dividend"] = div_info["annual_dividend"]
            entry["week52_high"] = round(float(info.get("fiftyTwoWeekHigh") or 0), 2)
            entry["week52_low"] = round(float(info.get("fiftyTwoWeekLow") or 0), 2)
        except Exception as e:
            print(f"Error fetching extended info for {ticker}: {e}")
        results[ticker] = entry
    return results


def fetch_news_for_tickers(tickers: list[str]) -> list[dict]:
    """Fetch recent news articles for multiple tickers via yfinance."""
    if not tickers:
        return []
    session = _get_session()
    seen_ids = set()
    articles = []
    for ticker in tickers:
        try:
            t = yf.Ticker(ticker, session=session)
            news = t.news or []
            for item in news:
                content = item.get("content") or item
                uid = content.get("id") or item.get("id") or item.get("uuid") or ""
                if not uid or uid in seen_ids:
                    continue
                seen_ids.add(uid)

                # Extract link from nested canonicalUrl or clickThroughUrl
                link = ""
                for url_key in ("canonicalUrl", "clickThroughUrl"):
                    url_obj = content.get(url_key)
                    if isinstance(url_obj, dict) and url_obj.get("url"):
                        link = url_obj["url"]
                        break
                    elif isinstance(url_obj, str) and url_obj:
                        link = url_obj
                        break
                if not link:
                    link = content.get("link") or item.get("link") or ""

                # Extract publisher from nested provider
                publisher = ""
                provider = content.get("provider")
                if isinstance(provider, dict):
                    publisher = provider.get("displayName") or ""
                if not publisher:
                    publisher = content.get("publisher") or item.get("publisher") or ""

                # Extract thumbnail
                thumbnail = ""
                thumb_data = content.get("thumbnail") or item.get("thumbnail")
                if isinstance(thumb_data, dict):
                    resolutions = thumb_data.get("resolutions") or []
                    if resolutions:
                        thumbnail = resolutions[-1].get("url", "")

                # Extract publish date (ISO string or unix timestamp)
                published_at = ""
                pub_date = content.get("pubDate") or ""
                if pub_date:
                    published_at = pub_date
                else:
                    pub_time = item.get("providerPublishTime")
                    if pub_time:
                        published_at = datetime.fromtimestamp(pub_time, tz=timezone.utc).isoformat()

                title = content.get("title") or item.get("title") or ""
                if not title or not link:
                    continue

                articles.append({
                    "uuid": uid,
                    "title": title,
                    "link": link,
                    "publisher": publisher,
                    "published_at": published_at,
                    "thumbnail": thumbnail,
                    "ticker": ticker.upper(),
                })
        except Exception as e:
            print(f"Error fetching news for {ticker}: {e}")
    return articles


def is_market_open() -> bool:
    """Check if US stock market is currently open (9:30 AM - 4:00 PM ET, Mon-Fri)."""
    from zoneinfo import ZoneInfo

    now = datetime.now(ZoneInfo("America/New_York"))
    if now.weekday() >= 5:
        return False
    market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
    return market_open <= now <= market_close
