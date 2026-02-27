from flask import Flask, request, jsonify
from flask_cors import CORS
from sqlalchemy import text
from models import db, Stock, Property
from services.stock_service import fetch_stock_data, fetch_batch_prices, is_market_open
from services.redfin_service import get_property_data, get_property_data_from_url, scrape_redfin_estimate
from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, timezone
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
            pass  # column may already exist


# ---------------------------------------------------------------------------
# Background scheduler: update stock prices every 5 seconds during market hours
# ---------------------------------------------------------------------------

def update_all_stock_prices():
    with app.app_context():
        stocks = Stock.query.all()
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


scheduler = BackgroundScheduler(daemon=True)
scheduler.add_job(update_all_stock_prices, "interval", seconds=5, id="stock_updater")
scheduler.start()
atexit.register(lambda: scheduler.shutdown(wait=False))


# ---------------------------------------------------------------------------
# Portfolio summary
# ---------------------------------------------------------------------------

@app.route("/api/portfolio", methods=["GET"])
def get_portfolio():
    stocks = Stock.query.all()
    properties = Property.query.all()

    total_stock_value = sum(s.shares * (s.current_price or 0) for s in stocks)
    total_property_equity = sum((p.estimated_value or 0) - (p.mortgage_amount or 0) for p in properties)

    total_value = total_stock_value + total_property_equity

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
        "stock_by_category": {k: round(v, 2) for k, v in stock_by_category.items()},
        "stock_count": len(stocks),
        "property_count": len(properties),
        "market_open": is_market_open(),
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
        last_updated=datetime.now(timezone.utc),
    )
    db.session.add(stock)
    db.session.commit()
    return jsonify(stock.to_dict()), 201


@app.route("/api/stocks/<int:stock_id>", methods=["PUT"])
def update_stock(stock_id):
    stock = Stock.query.get_or_404(stock_id)
    data = request.get_json()

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
    data = fetch_stock_data(stock.ticker)
    stock.current_price = data["current_price"]
    stock.company_name = data.get("company_name") or stock.company_name
    stock.last_updated = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(stock.to_dict())


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
