import yfinance as yf
from datetime import datetime, timezone


# Use curl_cffi to bypass Yahoo's TLS fingerprinting / bot protection
def _get_session():
    try:
        from curl_cffi import requests
        return requests.Session(impersonate="chrome", timeout=10)
    except ImportError:
        return None


def build_occ_symbol(ticker: str, expiration: str, option_type: str, strike: float) -> str:
    """Build an OCC option contract symbol.

    Format: {TICKER}{YYMMDD}{C|P}{strike * 1000, zero-padded to 8 digits}
    Example: AAPL + 240119 + C + 00150000 -> AAPL240119C00150000
    """
    ticker = (ticker or "").strip().upper()
    exp = datetime.strptime(expiration, "%Y-%m-%d").strftime("%y%m%d")
    cp = "C" if (option_type or "call").lower().startswith("c") else "P"
    strike_part = f"{int(round(float(strike) * 1000)):08d}"
    return f"{ticker}{exp}{cp}{strike_part}"


def _option_price_from_row(row) -> float:
    """Pick a sensible price from a chain row: lastPrice, else mid of bid/ask."""
    last = float(row.get("lastPrice") or 0)
    if last > 0:
        return round(last, 2)
    bid = float(row.get("bid") or 0)
    ask = float(row.get("ask") or 0)
    if bid > 0 and ask > 0:
        return round((bid + ask) / 2, 2)
    return round(bid or ask or 0, 2)


def get_option_expirations(ticker: str) -> list[str]:
    """Return available expiration dates (YYYY-MM-DD) for a ticker."""
    if not ticker:
        return []
    try:
        session = _get_session()
        t = yf.Ticker(ticker.strip().upper(), session=session)
        return list(t.options or [])
    except Exception as e:
        print(f"Error fetching expirations for {ticker}: {e}")
        return []


def get_option_strikes(ticker: str, expiration: str) -> dict:
    """Return available strikes for calls and puts for a given expiration."""
    result = {"calls": [], "puts": []}
    if not ticker or not expiration:
        return result
    try:
        session = _get_session()
        t = yf.Ticker(ticker.strip().upper(), session=session)
        chain = t.option_chain(expiration)
        if chain.calls is not None and not chain.calls.empty:
            result["calls"] = sorted(float(s) for s in chain.calls["strike"].dropna().tolist())
        if chain.puts is not None and not chain.puts.empty:
            result["puts"] = sorted(float(s) for s in chain.puts["strike"].dropna().tolist())
    except Exception as e:
        print(f"Error fetching strikes for {ticker} {expiration}: {e}")
    return result


def fetch_option_data(ticker: str, expiration: str, strike: float, option_type: str) -> dict:
    """Resolve a specific option contract and return its current price + metadata."""
    ticker = (ticker or "").strip().upper()
    option_type = (option_type or "call").lower()
    strike = float(strike)
    result = {
        "contract_symbol": build_occ_symbol(ticker, expiration, option_type, strike),
        "current_price": 0.0,
        "underlying_name": ticker,
    }
    try:
        session = _get_session()
        t = yf.Ticker(ticker, session=session)
        chain = t.option_chain(expiration)
        df = chain.calls if option_type.startswith("c") else chain.puts
        if df is not None and not df.empty:
            match = df[df["strike"] == strike]
            if not match.empty:
                row = match.iloc[0].to_dict()
                result["current_price"] = _option_price_from_row(row)
                if row.get("contractSymbol"):
                    result["contract_symbol"] = str(row["contractSymbol"])
        try:
            info = t.info or {}
            result["underlying_name"] = info.get("shortName") or info.get("longName") or ticker
        except Exception:
            pass
    except Exception as e:
        print(f"Error fetching option data for {ticker} {expiration} {strike} {option_type}: {e}")
    return result


def fetch_batch_option_prices(contract_symbols: list[str]) -> dict[str, float]:
    """Fetch current per-share prices for multiple option contract symbols."""
    if not contract_symbols:
        return {}
    session = _get_session()
    results = {}
    for symbol in contract_symbols:
        if not symbol:
            continue
        price = 0.0
        try:
            t = yf.Ticker(symbol, session=session)
            hist = t.history(period="1d")
            if not hist.empty:
                price = float(hist["Close"].iloc[-1])
            if price <= 0 and hasattr(t, "fast_info"):
                try:
                    fi = t.fast_info
                    if getattr(fi, "last_price", None):
                        price = float(fi.last_price)
                except Exception:
                    pass
            if price <= 0:
                try:
                    info = t.info or {}
                    price = float(info.get("lastPrice") or info.get("regularMarketPrice") or 0)
                except Exception:
                    pass
        except Exception as e:
            print(f"Error fetching option price for {symbol}: {e}")
        results[symbol] = round(price, 2)
    return results
