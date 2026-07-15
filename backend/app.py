from flask import Flask, request, jsonify
from flask_cors import CORS
from sqlalchemy import text
from models import db, Stock, Property, PortfolioSnapshot, Option, User
from services.stock_service import fetch_stock_data, fetch_batch_prices, fetch_batch_extended_info, is_market_open
from services.options_service import (
    fetch_option_data, fetch_batch_option_prices,
    get_option_expirations, get_option_strikes,
)
from services.redfin_service import get_property_data, get_property_data_from_url, scrape_redfin_estimate
from apscheduler.schedulers.background import BackgroundScheduler
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer
from functools import wraps
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
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "dev-secret-change-me")

# Stateless signed tokens for auth (no server-side session store required)
_token_serializer = URLSafeTimedSerializer(app.config["SECRET_KEY"], salt="auth-token")
_TOKEN_MAX_AGE = 60 * 60 * 24 * 30  # 30 days

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
        # Migration: add owner_id to per-account tables
        for _table in ("stocks", "options", "properties", "portfolio_snapshots"):
            try:
                db.session.execute(text(f"ALTER TABLE {_table} ADD COLUMN owner_id INTEGER"))
                db.session.commit()
            except Exception:
                db.session.rollback()

    # Seed the root account and claim any pre-existing (unowned) data as root's.
    _root_username = os.environ.get("ROOT_USERNAME", "root")
    _root_password = os.environ.get("ROOT_PASSWORD", "root")
    root_user = User.query.filter_by(role="root").first()
    if not root_user:
        root_user = User.query.filter_by(username=_root_username).first()
    if not root_user:
        root_user = User(
            username=_root_username,
            password_hash=generate_password_hash(_root_password),
            role="root",
        )
        db.session.add(root_user)
        db.session.commit()
    for _Model in (Stock, Option, Property, PortfolioSnapshot):
        _Model.query.filter(_Model.owner_id.is_(None)).update(
            {_Model.owner_id: root_user.id}, synchronize_session=False
        )
    db.session.commit()


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
    """Record current portfolio value per account for the history chart."""
    with app.app_context():
        now = datetime.now(timezone.utc)
        added = False
        for user in User.query.all():
            stocks = Stock.query.filter_by(owner_id=user.id).all()
            properties = Property.query.filter_by(owner_id=user.id).all()
            options = Option.query.filter_by(owner_id=user.id).all()
            stock_value = sum(s.shares * (s.current_price or 0) for s in stocks)
            property_equity = sum((p.estimated_value or 0) - (p.mortgage_amount or 0) for p in properties)
            options_value = sum((o.current_price or 0) * 100 * (o.contracts or 0) for o in options)
            total_value = stock_value + property_equity + options_value
            if total_value <= 0:
                continue
            db.session.add(PortfolioSnapshot(
                owner_id=user.id,
                timestamp=now,
                total_value=round(total_value, 2),
                stock_value=round(stock_value, 2),
                property_equity=round(property_equity, 2),
                options_value=round(options_value, 2),
            ))
            added = True
        if added:
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
# Authentication helpers
# ---------------------------------------------------------------------------

def _make_token(user):
    return _token_serializer.dumps({"uid": user.id, "role": user.role})


def get_current_user():
    """Return the authenticated User from the Bearer token, or None."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return None
    token = auth[len("Bearer "):].strip()
    try:
        payload = _token_serializer.loads(token, max_age=_TOKEN_MAX_AGE)
    except Exception:
        return None
    uid = payload.get("uid")
    if not uid:
        return None
    return db.session.get(User, uid)


def get_root_user():
    return User.query.filter_by(role="root").first()


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if not user:
            return jsonify({"error": "Authentication required"}), 401
        request.current_user = user
        return fn(*args, **kwargs)
    return wrapper


def root_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        user = get_current_user()
        if not user or user.role != "root":
            return jsonify({"error": "Root access required"}), 403
        request.current_user = user
        return fn(*args, **kwargs)
    return wrapper


def resolve_view():
    """Determine which portfolio to read and whether to mask dollar values.

    Returns (owner_id, masked, current_user). Data is masked unless the
    authenticated user is viewing their OWN portfolio.
    """
    current = get_current_user()
    view = (request.args.get("view") or "root").lower()
    if view == "self" and current:
        return current.id, False, current
    root = get_root_user()
    owner_id = root.id if root else None
    masked = current is None or owner_id is None or current.id != owner_id
    return owner_id, masked, current


# ---------------------------------------------------------------------------
# Authentication endpoints
# ---------------------------------------------------------------------------

@app.route("/api/auth/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400
    user = User.query.filter_by(username=username).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({"error": "Invalid username or password"}), 401
    return jsonify({"token": _make_token(user), "username": user.username, "role": user.role})


@app.route("/api/auth/me", methods=["GET"])
def me():
    user = get_current_user()
    if not user:
        return jsonify({"error": "Not authenticated"}), 401
    return jsonify(user.to_dict())


@app.route("/api/users", methods=["GET"])
@root_required
def list_users():
    users = User.query.filter_by(role="private").order_by(User.username).all()
    return jsonify({"users": [u.to_dict() for u in users]})


@app.route("/api/users", methods=["POST"])
@root_required
def create_user():
    data = request.get_json() or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""
    if not username or not password:
        return jsonify({"error": "Username and password are required"}), 400
    if User.query.filter_by(username=username).first():
        return jsonify({"error": "Username already exists"}), 409
    user = User(
        username=username,
        password_hash=generate_password_hash(password),
        role="private",
    )
    db.session.add(user)
    db.session.commit()
    return jsonify(user.to_dict()), 201


# ---------------------------------------------------------------------------
# Portfolio summary
# ---------------------------------------------------------------------------

@app.route("/api/portfolio", methods=["GET"])
def get_portfolio():
    owner_id, masked, _ = resolve_view()
    stocks = Stock.query.filter_by(owner_id=owner_id).all()
    properties = Property.query.filter_by(owner_id=owner_id).all()
    options = Option.query.filter_by(owner_id=owner_id).all()

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

    # Stock value by category
    stock_by_category = {}
    for s in stocks:
        cat = (s.category or "individual").lower()
        if cat not in ("individual", "diversified", "cash_equivalent"):
            cat = "individual"
        val = s.shares * (s.current_price or 0)
        stock_by_category[cat] = stock_by_category.get(cat, 0) + val

    # Distribution segments (percentages always present so charts work when masked)
    _segments = [
        ("individual", "Individual", stock_by_category.get("individual", 0)),
        ("diversified", "Diversified", stock_by_category.get("diversified", 0)),
        ("cash_equivalent", "Cash Equivalent", stock_by_category.get("cash_equivalent", 0)),
        ("options", "Options", total_options_value),
        ("real_estate", "Real Estate", total_property_equity),
    ]
    distribution = [
        {
            "key": key,
            "label": label,
            "pct": round(val / total_value * 100, 2) if total_value else 0,
            "value": None if masked else round(val, 2),
        }
        for key, label, val in _segments if val > 0
    ]

    return jsonify({
        "masked": masked,
        "total_value": None if masked else round(total_value, 2),
        "stock_value": None if masked else round(total_stock_value, 2),
        "property_equity": None if masked else round(total_property_equity, 2),
        "options_value": None if masked else round(total_options_value, 2),
        "total_day_change": None if masked else round(total_day_change, 2),
        "total_day_change_pct": total_day_change_pct,
        "total_annual_dividends": None if masked else round(total_annual_dividends, 2),
        "stock_by_category": None if masked else {k: round(v, 2) for k, v in stock_by_category.items()},
        "distribution": distribution,
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
    owner_id, masked, _ = resolve_view()
    period = request.args.get("period", "1M")
    period_map = {"1D": 1, "1W": 7, "1M": 30, "3M": 90, "1Y": 365, "2Y": 730, "3Y": 1095, "5Y": 1825, "10Y": 3650, "ALL": None}
    days = period_map.get(period, 30)

    # History reveals dollar values over time, so it is hidden entirely when masked.
    if masked:
        return jsonify({"period": period, "masked": True, "snapshots": []})

    query = PortfolioSnapshot.query.filter_by(owner_id=owner_id).order_by(PortfolioSnapshot.timestamp.asc())
    if days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        query = query.filter(PortfolioSnapshot.timestamp >= cutoff)

    snapshots = query.all()
    return jsonify({
        "period": period,
        "masked": False,
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
    owner_id, masked, _ = resolve_view()
    stocks = Stock.query.filter_by(owner_id=owner_id).order_by(Stock.ticker).all()

    def _mv(s):
        return s.shares * (s.current_price or 0)

    # Group totals mirror the frontend grouping: individual vs (diversified + cash).
    group_totals = {}
    for s in stocks:
        group = "individual" if (s.category or "individual").lower() == "individual" else "other"
        group_totals[group] = group_totals.get(group, 0) + _mv(s)

    properties = Property.query.filter_by(owner_id=owner_id).all()
    options = Option.query.filter_by(owner_id=owner_id).all()
    portfolio_total = (
        sum(_mv(s) for s in stocks)
        + sum((p.estimated_value or 0) - (p.mortgage_amount or 0) for p in properties)
        + sum((o.current_price or 0) * 100 * (o.contracts or 0) for o in options)
    )

    result = []
    for s in stocks:
        d = s.to_dict(masked=masked)
        v = _mv(s)
        group = "individual" if (s.category or "individual").lower() == "individual" else "other"
        gt = group_totals.get(group, 0)
        d["pct_of_group"] = round(v / gt * 100, 2) if gt else 0
        d["pct_of_portfolio"] = round(v / portfolio_total * 100, 2) if portfolio_total else 0
        result.append(d)

    return jsonify({
        "stocks": result,
        "masked": masked,
        "market_open": is_market_open(),
    })


@app.route("/api/stocks", methods=["POST"])
@login_required
def add_stock():
    owner_id = request.current_user.id
    data = request.get_json()
    is_cash = bool(data.get("is_cash"))

    if is_cash:
        label = (data.get("ticker") or data.get("label") or "Cash").strip() or "Cash"
        amount = float(data.get("amount", data.get("current_price", 0)) or 0)
        if amount <= 0:
            return jsonify({"error": "A positive cash amount is required"}), 400
        stock = Stock(
            owner_id=owner_id,
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
        owner_id=owner_id,
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


def _get_owned_or_error(model, obj_id):
    """Fetch a row that belongs to the authenticated user, or an error response."""
    user = get_current_user()
    if not user:
        return None, (jsonify({"error": "Authentication required"}), 401)
    obj = db.session.get(model, obj_id)
    if not obj:
        return None, (jsonify({"error": "Not found"}), 404)
    if obj.owner_id != user.id:
        return None, (jsonify({"error": "You can only modify your own portfolio"}), 403)
    return obj, None


@app.route("/api/stocks/<int:stock_id>", methods=["PUT"])
def update_stock(stock_id):
    stock, err = _get_owned_or_error(Stock, stock_id)
    if err:
        return err
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
    stock, err = _get_owned_or_error(Stock, stock_id)
    if err:
        return err
    db.session.delete(stock)
    db.session.commit()
    return jsonify({"message": "Stock deleted"}), 200


@app.route("/api/stocks/<int:stock_id>/refresh", methods=["POST"])
def refresh_stock(stock_id):
    stock, err = _get_owned_or_error(Stock, stock_id)
    if err:
        return err
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
    owner_id, masked, _ = resolve_view()
    options = Option.query.filter_by(owner_id=owner_id).order_by(
        Option.underlying_ticker, Option.expiration
    ).all()

    stocks = Stock.query.filter_by(owner_id=owner_id).all()
    properties = Property.query.filter_by(owner_id=owner_id).all()
    portfolio_total = (
        sum(s.shares * (s.current_price or 0) for s in stocks)
        + sum((p.estimated_value or 0) - (p.mortgage_amount or 0) for p in properties)
        + sum((o.current_price or 0) * 100 * (o.contracts or 0) for o in options)
    )

    result = []
    for o in options:
        d = o.to_dict(masked=masked)
        mv = (o.current_price or 0) * 100 * (o.contracts or 0)
        d["pct_of_portfolio"] = round(mv / portfolio_total * 100, 2) if portfolio_total else 0
        result.append(d)

    return jsonify({
        "options": result,
        "masked": masked,
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
@login_required
def add_option():
    owner_id = request.current_user.id
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
        owner_id=owner_id,
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
    option, err = _get_owned_or_error(Option, option_id)
    if err:
        return err
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
    option, err = _get_owned_or_error(Option, option_id)
    if err:
        return err
    db.session.delete(option)
    db.session.commit()
    return jsonify({"message": "Option deleted"}), 200


@app.route("/api/options/<int:option_id>/refresh", methods=["POST"])
def refresh_option(option_id):
    option, err = _get_owned_or_error(Option, option_id)
    if err:
        return err
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
    owner_id, masked, _ = resolve_view()
    properties = Property.query.filter_by(owner_id=owner_id).order_by(Property.address).all()

    stocks = Stock.query.filter_by(owner_id=owner_id).all()
    options = Option.query.filter_by(owner_id=owner_id).all()
    portfolio_total = (
        sum(s.shares * (s.current_price or 0) for s in stocks)
        + sum((p.estimated_value or 0) - (p.mortgage_amount or 0) for p in properties)
        + sum((o.current_price or 0) * 100 * (o.contracts or 0) for o in options)
    )

    result = []
    for p in properties:
        d = p.to_dict(masked=masked)
        equity = (p.estimated_value or 0) - (p.mortgage_amount or 0)
        d["pct_of_portfolio"] = round(equity / portfolio_total * 100, 2) if portfolio_total else 0
        result.append(d)

    return jsonify({"properties": result, "masked": masked})


@app.route("/api/properties", methods=["POST"])
@login_required
def add_property():
    owner_id = request.current_user.id
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
        owner_id=owner_id,
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
    prop, err = _get_owned_or_error(Property, prop_id)
    if err:
        return err
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
    prop, err = _get_owned_or_error(Property, prop_id)
    if err:
        return err
    db.session.delete(prop)
    db.session.commit()
    return jsonify({"message": "Property deleted"}), 200


@app.route("/api/properties/<int:prop_id>/refresh", methods=["POST"])
def refresh_property(prop_id):
    prop, err = _get_owned_or_error(Property, prop_id)
    if err:
        return err

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
