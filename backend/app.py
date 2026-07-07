from flask import Flask, request, jsonify
from flask_cors import CORS
from sqlalchemy import text
from models import db, Stock, Property, PortfolioSnapshot, Option
from services.stock_service import fetch_stock_data, fetch_batch_prices, fetch_batch_extended_info, is_market_open
from services.options_service import (
    fetch_option_data, fetch_batch_option_prices,
    get_option_expirations, get_option_strikes,
)
from services.redfin_service import get_property_data, get_property_data_from_url, scrape_redfin_estimate
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timezone, timedelta
import atexit
import os

app = Flask(__name__)
CORS(app)

# Use SQLite by default (no setup required). Set DATABASE_URL for MySQL.
_instance_dir = os.path.join(os.path.dirname(__file__), "instance")
_default_db = os.path.join(_instance_dir, "portfolio.db").replace("\\", "/")
_db_url = os.environ.get("DATABASE_URL", "sqlite:///" + _default_db)
if "sqlite" in _db_url:
    os.makedirs(_instance_dir, exist_ok=True)
app.config["SQLALCHEMY_DATABASE_URI"] = _db_url
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

with app.app_context():
    db.create_all()
    # Migration: add mortgage_amount if missing (replaces purchase_price)
    if "sqlite" in _db_url:
        try:
            db.session.execute(text("ALTER TABLE properties ADD COLUMN mortgage_amount REAL DEFAULT 0"))
            db.session.commit()
        except Exception:
            db.session.rollback()
            pass  # column may already exist
        # Migration: add category to stocks
        try:
            db.session.execute(text("ALTER TABLE stocks ADD COLUMN category VARCHAR(30) DEFAULT 'individual'"))
            db.session.commit()
        except Exception:
            db.session.rollback()
        # Migration: add is_cash flag for plain cash entries
        try:
            db.session.execute(text("ALTER TABLE stocks ADD COLUMN is_cash BOOLEAN DEFAULT 0"))
            db.session.commit()
        except Exception:
            db.session.rollback()
        # Migration: add options_value to snapshots
        try:
            db.session.execute(text("ALTER TABLE portfolio_snapshots ADD COLUMN options_value REAL DEFAULT 0"))
            db.session.commit()
        except Exception:
            db.session.rollback()
        for col in [
            "previous_close REAL DEFAULT 0",
            "dividend_yield REAL DEFAULT 0",
            "annual_dividend REAL DEFAULT 0",
            "week52_high REAL DEFAULT 0",
            "week52_low REAL DEFAULT 0",
        ]:
            try:
                db.session.execute(text(f"ALTER TABLE stocks ADD COLUMN {col}"))
                db.session.commit()
            except Exception:
                db.session.rollback()


# ---------------------------------------------------------------------------
# Background scheduler: update stock prices every 15 seconds during market hours
# ---------------------------------------------------------------------------

def update_all_stock_prices():
    # Only poll the (free, unofficial) Yahoo Finance endpoint during market
    # hours to stay well under informal rate limits, especially from a
    # datacenter IP where blocks are more aggressive.
    if not is_market_open():
        return
    with app.app_context():
        stocks = [s for s in Stock.query.all() if not s.is_cash]
        if not stocks:
            return
        tickers = list({s.ticker.upper() for s in stocks})
        prices = fetch_batch_prices(tickers)
        now = datetime.now(timezone.utc)
        for stock in stocks:
            new_price = prices.get(stock.ticker.upper())
            if new_price and new_price > 0:
                stock.current_price = new_price
                stock.last_updated = now
        db.session.commit()


def update_all_option_prices():
    # Same market-hours guard as stock polling to conserve free-tier requests.
    if not is_market_open():
        return
    with app.app_context():
        options = Option.query.all()
        if not options:
            return
        symbols = list({o.contract_symbol for o in options if o.contract_symbol})
        prices = fetch_batch_option_prices(symbols)
        now = datetime.now(timezone.utc)
        for option in options:
            new_price = prices.get(option.contract_symbol)
            if new_price and new_price > 0:
                option.current_price = new_price
                option.last_updated = now
        db.session.commit()


def update_extended_info():
    """Refresh previous_close, dividends, and 52-week data (runs less frequently)."""
    with app.app_context():
        stocks = [s for s in Stock.query.all() if not s.is_cash]
        if not stocks:
            return
        tickers = list({s.ticker.upper() for s in stocks})
        extended = fetch_batch_extended_info(tickers)
        for stock in stocks:
            info = extended.get(stock.ticker.upper())
            if not info:
                continue
            if info["previous_close"]:
                stock.previous_close = info["previous_close"]
            if info["dividend_yield"]:
                stock.dividend_yield = info["dividend_yield"]
            if info["annual_dividend"]:
                stock.annual_dividend = info["annual_dividend"]
            if info["week52_high"]:
                stock.week52_high = info["week52_high"]
            if info["week52_low"]:
                stock.week52_low = info["week52_low"]
        db.session.commit()


def take_portfolio_snapshot():
    """Record current portfolio value for the history chart."""
    with app.app_context():
        stocks = Stock.query.all()
        properties = Property.query.all()
        options = Option.query.all()
        stock_value = sum(s.shares * (s.current_price or 0) for s in stocks)
        property_equity = sum((p.estimated_value or 0) - (p.mortgage_amount or 0) for p in properties)
        options_value = sum((o.current_price or 0) * 100 * (o.contracts or 0) for o in options)
        total_value = stock_value + property_equity + options_value
        if total_value <= 0:
            return
        snapshot = PortfolioSnapshot(
            timestamp=datetime.now(timezone.utc),
            total_value=round(total_value, 2),
            stock_value=round(stock_value, 2),
            property_equity=round(property_equity, 2),
            options_value=round(options_value, 2),
        )
        db.session.add(snapshot)
        db.session.commit()


scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(update_all_stock_prices, "interval", seconds=15, id="stock_updater")
scheduler.add_job(update_all_option_prices, "interval", seconds=15, id="option_updater")
scheduler.add_job(update_extended_info, "interval", minutes=30, id="extended_info_updater")
scheduler.add_job(take_portfolio_snapshot, "interval", minutes=30, id="snapshot_recorder")
scheduler.start()
atexit.register(lambda: scheduler.shutdown(wait=False))

# Take an initial snapshot and extended-info fetch on startup
with app.app_context():
    update_extended_info()
    take_portfolio_snapshot()


# ---------------------------------------------------------------------------
# Portfolio summary
# ---------------------------------------------------------------------------

@app.route("/api/portfolio", methods=["GET"])
def get_portfolio():
    stocks = Stock.query.all()
    properties = Property.query.all()
    options = Option.query.all()

    total_stock_value = sum(s.shares * (s.current_price or 0) for s in stocks)
    total_property_equity = sum((p.estimated_value or 0) - (p.mortgage_amount or 0) for p in properties)
    total_options_value = sum((o.current_price or 0) * 100 * (o.contracts or 0) for o in options)

    total_value = total_stock_value + total_property_equity + total_options_value

    # Day change across all stocks
    total_day_change = 0.0
    total_prev_value = 0.0
    for s in stocks:
        prev = s.previous_close or 0
        cur = s.current_price or 0
        total_day_change += (cur - prev) * s.shares
        total_prev_value += prev * s.shares
    total_day_change_pct = round(total_day_change / total_prev_value * 100, 2) if total_prev_value else 0

    # Dividend income
    total_annual_dividends = sum((s.annual_dividend or 0) * s.shares for s in stocks)

    # Stock value by category for distribution chart
    stock_by_category = {}
    for s in stocks:
        cat = (s.category or "individual").lower()
        if cat not in ("individual", "diversified", "cash_equivalent"):
            cat = "individual"
        val = s.shares * (s.current_price or 0)
        stock_by_category[cat] = stock_by_category.get(cat, 0) + val

    return jsonify({
        "total_value": round(total_value, 2),
        "stock_value": round(total_stock_value, 2),
        "property_equity": round(total_property_equity, 2),
        "options_value": round(total_options_value, 2),
        "total_day_change": round(total_day_change, 2),
        "total_day_change_pct": total_day_change_pct,
        "total_annual_dividends": round(total_annual_dividends, 2),
        "stock_by_category": {k: round(v, 2) for k, v in stock_by_category.items()},
        "stock_count": len(stocks),
        "property_count": len(properties),
        "option_count": len(options),
        "market_open": is_market_open(),
    })


# ---------------------------------------------------------------------------
# Portfolio history
# ---------------------------------------------------------------------------

@app.route("/api/portfolio/history", methods=["GET"])
def get_portfolio_history():
    period = request.args.get("period", "1M")
    period_map = {"1D": 1, "1W": 7, "1M": 30, "3M": 90, "1Y": 365, "2Y": 730, "3Y": 1095, "5Y": 1825, "10Y": 3650, "ALL": None}
    days = period_map.get(period, 30)

    query = PortfolioSnapshot.query.order_by(PortfolioSnapshot.timestamp.asc())
    if days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        query = query.filter(PortfolioSnapshot.timestamp >= cutoff)

    snapshots = query.all()
    return jsonify({
        "period": period,
        "snapshots": [
            {
                "timestamp": s.timestamp.isoformat(),
                "total_value": s.total_value,
                "stock_value": s.stock_value,
                "property_equity": s.property_equity,
                "options_value": s.options_value or 0,
            }
            for s in snapshots
        ],
    })


# ---------------------------------------------------------------------------
# Stocks CRUD
# ---------------------------------------------------------------------------

@app.route("/api/stocks", methods=["GET"])
def get_stocks():
    stocks = Stock.query.order_by(Stock.ticker).all()
    return jsonify({
        "stocks": [s.to_dict() for s in stocks],
        "market_open": is_market_open(),
    })


@app.route("/api/stocks", methods=["POST"])
def add_stock():
    data = request.get_json()
    is_cash = bool(data.get("is_cash"))

    if is_cash:
        label = (data.get("ticker") or data.get("label") or "Cash").strip() or "Cash"
        amount = float(data.get("amount", data.get("current_price", 0)) or 0)
        if amount <= 0:
            return jsonify({"error": "A positive cash amount is required"}), 400
        stock = Stock(
            ticker=label,
            company_name="Cash",
            shares=1,
            category="cash_equivalent",
            is_cash=True,
            current_price=amount,
            previous_close=0,
            last_updated=datetime.now(timezone.utc),
        )
        db.session.add(stock)
        db.session.commit()
        return jsonify(stock.to_dict()), 201

    ticker = data.get("ticker", "").strip().upper()
    shares = float(data.get("shares", 0))
    category = (data.get("category") or "individual").lower()
    if category not in ("individual", "diversified", "cash_equivalent"):
        category = "individual"

    if not ticker or shares <= 0:
        return jsonify({"error": "Ticker and positive shares are required"}), 400

    stock_data = fetch_stock_data(ticker)

    stock = Stock(
        ticker=ticker,
        company_name=stock_data["company_name"],
        shares=shares,
        category=category,
        current_price=stock_data["current_price"],
        previous_close=stock_data.get("previous_close", 0),
        dividend_yield=stock_data.get("dividend_yield", 0),
        annual_dividend=stock_data.get("annual_dividend", 0),
        week52_high=stock_data.get("week52_high", 0),
        week52_low=stock_data.get("week52_low", 0),
        last_updated=datetime.now(timezone.utc),
    )
    db.session.add(stock)
    db.session.commit()
    return jsonify(stock.to_dict()), 201


@app.route("/api/stocks/<int:stock_id>", methods=["PUT"])
def update_stock(stock_id):
    stock = Stock.query.get_or_404(stock_id)
    data = request.get_json()

    if stock.is_cash:
        if "ticker" in data or "label" in data:
            label = (data.get("ticker") or data.get("label") or stock.ticker).strip()
            if label:
                stock.ticker = label
        if "amount" in data or "current_price" in data:
            stock.current_price = float(data.get("amount", data.get("current_price")) or 0)
        stock.last_updated = datetime.now(timezone.utc)
        db.session.commit()
        return jsonify(stock.to_dict())

    if "shares" in data:
        stock.shares = float(data["shares"])
    if "category" in data:
        cat = (data["category"] or "individual").lower()
        if cat in ("individual", "diversified", "cash_equivalent"):
            stock.category = cat
    if "ticker" in data:
        new_ticker = data["ticker"].strip().upper()
        if new_ticker != stock.ticker:
            stock.ticker = new_ticker
            stock_data = fetch_stock_data(new_ticker)
            stock.company_name = stock_data["company_name"]
            stock.current_price = stock_data["current_price"]
            stock.previous_close = stock_data.get("previous_close", 0)
            stock.dividend_yield = stock_data.get("dividend_yield", 0)
            stock.annual_dividend = stock_data.get("annual_dividend", 0)
            stock.week52_high = stock_data.get("week52_high", 0)
            stock.week52_low = stock_data.get("week52_low", 0)

    stock.last_updated = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(stock.to_dict())


@app.route("/api/stocks/<int:stock_id>", methods=["DELETE"])
def delete_stock(stock_id):
    stock = Stock.query.get_or_404(stock_id)
    db.session.delete(stock)
    db.session.commit()
    return jsonify({"message": "Stock deleted"}), 200


@app.route("/api/stocks/<int:stock_id>/refresh", methods=["POST"])
def refresh_stock(stock_id):
    stock = Stock.query.get_or_404(stock_id)
    if stock.is_cash:
        return jsonify(stock.to_dict())
    data = fetch_stock_data(stock.ticker)
    stock.current_price = data["current_price"]
    stock.company_name = data.get("company_name") or stock.company_name
    stock.previous_close = data.get("previous_close", 0)
    stock.dividend_yield = data.get("dividend_yield", 0)
    stock.annual_dividend = data.get("annual_dividend", 0)
    stock.week52_high = data.get("week52_high", 0)
    stock.week52_low = data.get("week52_low", 0)
    stock.last_updated = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(stock.to_dict())


# ---------------------------------------------------------------------------
# Options CRUD
# ---------------------------------------------------------------------------

@app.route("/api/options", methods=["GET"])
def get_options():
    options = Option.query.order_by(Option.underlying_ticker, Option.expiration).all()
    return jsonify({
        "options": [o.to_dict() for o in options],
        "market_open": is_market_open(),
    })


@app.route("/api/options/chain", methods=["GET"])
def get_options_chain():
    ticker = request.args.get("ticker", "").strip().upper()
    expiration = request.args.get("expiration", "").strip()
    if not ticker:
        return jsonify({"error": "Ticker is required"}), 400
    if expiration:
        return jsonify({"ticker": ticker, "expiration": expiration, **get_option_strikes(ticker, expiration)})
    return jsonify({"ticker": ticker, "expirations": get_option_expirations(ticker)})


@app.route("/api/options", methods=["POST"])
def add_option():
    data = request.get_json()
    ticker = (data.get("underlying_ticker") or data.get("ticker") or "").strip().upper()
    option_type = (data.get("option_type") or "call").lower()
    if option_type not in ("call", "put"):
        option_type = "call"
    expiration = (data.get("expiration") or "").strip()
    try:
        strike = float(data.get("strike", 0))
        contracts = int(data.get("contracts", 0))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid strike or contracts"}), 400

    if not ticker or not expiration or strike <= 0 or contracts == 0:
        return jsonify({"error": "Ticker, expiration, positive strike, and contracts are required"}), 400

    info = fetch_option_data(ticker, expiration, strike, option_type)

    option = Option(
        underlying_ticker=ticker,
        underlying_name=info.get("underlying_name", ticker),
        option_type=option_type,
        strike=strike,
        expiration=expiration,
        contracts=contracts,
        contract_symbol=info.get("contract_symbol", ""),
        current_price=info.get("current_price", 0),
        last_updated=datetime.now(timezone.utc),
    )
    db.session.add(option)
    db.session.commit()
    return jsonify(option.to_dict()), 201


@app.route("/api/options/<int:option_id>", methods=["PUT"])
def update_option(option_id):
    option = Option.query.get_or_404(option_id)
    data = request.get_json()

    if "contracts" in data:
        try:
            option.contracts = int(data["contracts"])
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid contracts"}), 400

    option.last_updated = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(option.to_dict())


@app.route("/api/options/<int:option_id>", methods=["DELETE"])
def delete_option(option_id):
    option = Option.query.get_or_404(option_id)
    db.session.delete(option)
    db.session.commit()
    return jsonify({"message": "Option deleted"}), 200


@app.route("/api/options/<int:option_id>/refresh", methods=["POST"])
def refresh_option(option_id):
    option = Option.query.get_or_404(option_id)
    info = fetch_option_data(option.underlying_ticker, option.expiration, option.strike, option.option_type)
    if info.get("current_price"):
        option.current_price = info["current_price"]
    if info.get("contract_symbol"):
        option.contract_symbol = info["contract_symbol"]
    if info.get("underlying_name"):
        option.underlying_name = info["underlying_name"]
    option.last_updated = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(option.to_dict())


# ---------------------------------------------------------------------------
# Properties CRUD
# ---------------------------------------------------------------------------

@app.route("/api/properties", methods=["GET"])
def get_properties():
    properties = Property.query.order_by(Property.address).all()
    return jsonify({"properties": [p.to_dict() for p in properties]})


@app.route("/api/properties", methods=["POST"])
def add_property():
    data = request.get_json()
    address = data.get("address", "").strip()
    redfin_url = data.get("redfin_url", "").strip()
    mortgage_amount = float(data.get("mortgage_amount", 0))
    manual_estimated_value = data.get("estimated_value")

    if not address and not redfin_url:
        return jsonify({"error": "Address or Redfin link is required"}), 400

    if redfin_url:
        redfin_data = get_property_data_from_url(redfin_url)
    else:
        redfin_data = get_property_data(address)

    estimated_value = redfin_data.get("estimated_value", 0) if redfin_data else 0
    if manual_estimated_value is not None:
        try:
            v = float(manual_estimated_value)
            if v > 0:
                estimated_value = v
        except (ValueError, TypeError):
            pass

    prop = Property(
        address=redfin_data["address"] if redfin_data else (address or "Property"),
        redfin_url=redfin_data.get("redfin_url", redfin_url) if redfin_data else redfin_url,
        mortgage_amount=mortgage_amount,
        estimated_value=estimated_value,
        beds=redfin_data.get("beds", 0) if redfin_data else 0,
        baths=redfin_data.get("baths", 0) if redfin_data else 0,
        sqft=redfin_data.get("sqft", 0) if redfin_data else 0,
        last_updated=datetime.now(timezone.utc),
    )
    db.session.add(prop)
    db.session.commit()
    return jsonify(prop.to_dict()), 201


@app.route("/api/properties/<int:prop_id>", methods=["PUT"])
def update_property(prop_id):
    prop = Property.query.get_or_404(prop_id)
    data = request.get_json()

    if "address" in data:
        prop.address = data["address"].strip()
    if "redfin_url" in data:
        prop.redfin_url = data["redfin_url"].strip()
    if "mortgage_amount" in data:
        prop.mortgage_amount = float(data["mortgage_amount"])
    if "estimated_value" in data:
        prop.estimated_value = float(data["estimated_value"])

    prop.last_updated = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(prop.to_dict())


@app.route("/api/properties/<int:prop_id>", methods=["DELETE"])
def delete_property(prop_id):
    prop = Property.query.get_or_404(prop_id)
    db.session.delete(prop)
    db.session.commit()
    return jsonify({"message": "Property deleted"}), 200


@app.route("/api/properties/<int:prop_id>/refresh", methods=["POST"])
def refresh_property(prop_id):
    prop = Property.query.get_or_404(prop_id)

    if prop.redfin_url:
        details = scrape_redfin_estimate(prop.redfin_url)
    else:
        redfin_data = get_property_data(prop.address)
        if not redfin_data:
            return jsonify({"error": "Could not find property on Redfin"}), 404
        details = redfin_data
        prop.redfin_url = redfin_data.get("redfin_url", prop.redfin_url)

    if details.get("estimated_value"):
        prop.estimated_value = details["estimated_value"]
    if details.get("beds"):
        prop.beds = details["beds"]
    if details.get("baths"):
        prop.baths = details["baths"]
    if details.get("sqft"):
        prop.sqft = details["sqft"]

    prop.last_updated = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(prop.to_dict())


if __name__ == "__main__":
    app.run(debug=True, port=5001)
