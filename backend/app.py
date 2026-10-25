from flask import Flask, request, jsonify
from flask_cors import CORS
from sqlalchemy import func, text
from models import db, Stock, Property, PortfolioSnapshot, Option, User
from services.stock_service import fetch_stock_data, fetch_batch_prices, fetch_batch_extended_info, is_market_open
from services.options_service import (
    fetch_option_data, fetch_batch_option_prices,
    get_option_expirations, get_option_strikes,
)
from services.redfin_service import (
    RedfinBlockedError, get_property_data, get_property_data_from_url, scrape_redfin_estimate,
)
from apscheduler.schedulers.background import BackgroundScheduler
from werkzeug.security import generate_password_hash, check_password_hash
from itsdangerous import URLSafeTimedSerializer
from functools import wraps
from datetime import datetime, timezone, timedelta
import atexit
import os

# region agent log
import json as _dbg_json, time as _dbg_time, threading as _dbg_threading, tracemalloc as _dbg_tm, gc as _dbg_gc, subprocess as _dbg_sp
_DBG_PATH = "/Users/mrbanerjee/portfolio-tracker/.cursor/debug-e8da93.log"
_dbg_tm.start(1)
_DBG_BOOT = _dbg_time.time()
def _dbg(location, message, data, hypothesis_id, run_id="run1"):
    try:
        with open(_DBG_PATH, "a") as f:
            f.write(_dbg_json.dumps({"sessionId": "e8da93", "runId": run_id, "hypothesisId": hypothesis_id, "location": location, "message": message, "data": data, "timestamp": int(_dbg_time.time() * 1000)}) + "\n")
    except Exception:
        pass
def _dbg_rss_kb():
    try:
        return int(_dbg_sp.run(["ps", "-o", "rss=", "-p", str(os.getpid())], capture_output=True, text=True, timeout=5).stdout.strip() or 0)
    except Exception:
        return -1
_dbg("app.py:boot", "process boot start", {"pid": os.getpid(), "ppid": os.getppid(), "rss_kb": _dbg_rss_kb()}, "E")
# endregion

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


def _drop_legacy_purchase_price():
    """Remove leftover purchase_price so property inserts no longer 500."""
    try:
        cols = db.session.execute(text("PRAGMA table_info(properties)")).fetchall()
        names = {row[1] for row in cols}
        if "purchase_price" not in names:
            return
        if "mortgage_amount" in names:
            db.session.execute(text(
                "UPDATE properties SET mortgage_amount = purchase_price "
                "WHERE (mortgage_amount IS NULL OR mortgage_amount = 0) "
                "AND purchase_price IS NOT NULL"
            ))
            db.session.commit()
        try:
            db.session.execute(text("ALTER TABLE properties DROP COLUMN purchase_price"))
            db.session.commit()
            return
        except Exception:
            db.session.rollback()
        db.session.execute(text(
            """
            CREATE TABLE properties_new (
                id INTEGER NOT NULL PRIMARY KEY AUTOINCREMENT,
                owner_id INTEGER,
                address VARCHAR(500) NOT NULL,
                redfin_url VARCHAR(1000),
                mortgage_amount FLOAT DEFAULT 0,
                estimated_value FLOAT DEFAULT 0,
                beds FLOAT DEFAULT 0,
                baths FLOAT DEFAULT 0,
                sqft INTEGER DEFAULT 0,
                last_updated DATETIME
            )
            """
        ))
        db.session.execute(text(
            """
            INSERT INTO properties_new (
                id, owner_id, address, redfin_url, mortgage_amount,
                estimated_value, beds, baths, sqft, last_updated
            )
            SELECT id, owner_id, address, redfin_url, mortgage_amount,
                   estimated_value, beds, baths, sqft, last_updated
            FROM properties
            """
        ))
        db.session.execute(text("DROP TABLE properties"))
        db.session.execute(text("ALTER TABLE properties_new RENAME TO properties"))
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"purchase_price migration skipped: {e}")


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
        # Old schema had NOT NULL purchase_price; the model now uses mortgage_amount.
        _drop_legacy_purchase_price()
        try:
            db.session.execute(text("ALTER TABLE options ADD COLUMN position VARCHAR(3) DEFAULT 'bto'"))
            db.session.commit()
        except Exception:
            db.session.rollback()
        for col in [
            "redfin_estimate REAL DEFAULT 0",
            "last_sold_price REAL DEFAULT 0",
            "value_source VARCHAR(20) DEFAULT ''",
        ]:
            try:
                db.session.execute(text(f"ALTER TABLE properties ADD COLUMN {col}"))
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
            options_value = sum(o.market_value for o in options)
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

# region agent log
from apscheduler.events import EVENT_JOB_ERROR, EVENT_JOB_MISSED, EVENT_JOB_MAX_INSTANCES, EVENT_JOB_EXECUTED
_dbg_job_last = {}
def _dbg_job_event(ev):
    if ev.code == EVENT_JOB_EXECUTED:
        if ev.job_id in ("stock_updater", "option_updater"):
            dur = (datetime.now(timezone.utc) - ev.scheduled_run_time).total_seconds()
            if dur > 10 or _dbg_job_last.get(ev.job_id, 0) + 300 < _dbg_time.time():
                _dbg_job_last[ev.job_id] = _dbg_time.time()
                _dbg("app.py:job_event", "job executed", {"job": ev.job_id, "seconds_since_scheduled": round(dur, 2), "market_open": is_market_open()}, "D")
        return
    _dbg("app.py:job_event", "job problem", {"job": ev.job_id, "code": {EVENT_JOB_ERROR: "error", EVENT_JOB_MISSED: "missed", EVENT_JOB_MAX_INSTANCES: "max_instances"}.get(ev.code, ev.code), "exception": repr(getattr(ev, "exception", None))[:300]}, "D")
scheduler.add_listener(_dbg_job_event, EVENT_JOB_ERROR | EVENT_JOB_MISSED | EVENT_JOB_MAX_INSTANCES | EVENT_JOB_EXECUTED)
def _dbg_monitor():
    import yfinance.shared as _yfs
    from services import stock_service as _ss, options_service as _os
    cur, peak = _dbg_tm.get_traced_memory()
    try:
        fds = len(os.listdir("/dev/fd"))
    except Exception:
        fds = -1
    with app.app_context():
        snaps = PortfolioSnapshot.query.count()
    _dbg("app.py:monitor", "memory sample", {
        "pid": os.getpid(), "uptime_s": int(_dbg_time.time() - _DBG_BOOT), "rss_kb": _dbg_rss_kb(),
        "py_traced_kb": cur // 1024, "py_peak_kb": peak // 1024, "gc_objects": len(_dbg_gc.get_objects()),
        "threads": _dbg_threading.active_count(), "open_fds": fds,
        "yf_dfs": len(_yfs._DFS), "yf_errors": len(_yfs._ERRORS), "yf_tracebacks": len(_yfs._TRACEBACKS),
        "snapshot_rows": snaps, "market_open": is_market_open(),
        "stock_session_max_concurrent": _ss._DBG_MAX_INFLIGHT, "options_session_max_concurrent": _os._DBG_MAX_INFLIGHT,
    }, "A,B,C,D")
scheduler.add_job(_dbg_monitor, "interval", seconds=60, id="dbg_monitor")
_dbg_boot_t0 = _dbg_time.time()
# endregion

scheduler.start()
atexit.register(lambda: scheduler.shutdown(wait=False))

# Take an initial snapshot and extended-info fetch on startup
with app.app_context():
    update_extended_info()
    take_portfolio_snapshot()

# region agent log
_dbg("app.py:boot", "startup jobs finished (blocks worker boot)", {"pid": os.getpid(), "startup_seconds": round(_dbg_time.time() - _dbg_boot_t0, 2), "rss_kb": _dbg_rss_kb()}, "E")
# endregion


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

    Returns (scope, masked, current_user). scope is a single owner_id, or None
    for the root view, which combines every account. Any authenticated user may
    see real dollar values; values are only masked for anonymous (logged-out)
    visitors. The root user may also target any account by its numeric id.
    """
    current = get_current_user()
    view = (request.args.get("view") or "root").lower()
    if view == "self" and current and current.role != "root":
        return current.id, False, current
    # Root can inspect any account (e.g. a private account) by its id.
    if current and current.role == "root" and view.isdigit():
        target = db.session.get(User, int(view))
        if target:
            return target.id, False, current
    return None, current is None, current


def _holdings(model, scope):
    """Query a holdings table for one account, or every account when scope is None."""
    query = model.query
    return query if scope is None else query.filter_by(owner_id=scope)


def _merge_rows(rows, key, count_field, masked):
    """Collapse rows sharing `key` into one dict for the combined root view.

    Returns [(dict, market_value)]. count_field ("shares" or "contracts") is
    summed; the row with the largest count supplies every other field.
    """
    groups = {}
    for row in rows:
        groups.setdefault(key(row), []).append(row)
    merged = []
    for group_key, group in groups.items():
        lead = max(group, key=lambda r: getattr(r, count_field) or 0)
        d = lead.to_dict()
        value = sum(_row_value(r) for r in group)
        d["id"] = "agg-" + "-".join(str(k) for k in group_key)
        d[count_field] = sum(getattr(r, count_field) or 0 for r in group)
        d["market_value"] = round(value, 2)
        d["account_count"] = len({r.owner_id for r in group})
        if masked:
            for field in type(lead).MASKED_FIELDS:
                d[field] = None
        merged.append((d, value))
    return merged


def _row_value(row):
    if isinstance(row, Option):
        return row.market_value
    return row.shares * (row.current_price or 0)


def _option_key(o):
    return (o.underlying_ticker, o.option_type or "call", o.strike, o.expiration, o.position or "bto")


def _merge_stocks(stocks, masked):
    cash = [s for s in stocks if s.is_cash]
    merged = _merge_rows(
        [s for s in stocks if not s.is_cash], lambda s: (s.ticker.upper(),), "shares", masked
    )
    if cash:
        total = sum(_row_value(s) for s in cash)
        d = cash[0].to_dict()
        d.update({
            "id": "agg-cash",
            "ticker": "Cash",
            "shares": 1,
            "current_price": round(total, 2),
            "market_value": round(total, 2),
            "account_count": len({s.owner_id for s in cash}),
        })
        if masked:
            for field in Stock.MASKED_FIELDS:
                d[field] = None
        merged.append((d, total))
    merged.sort(key=lambda item: (item[0]["is_cash"], item[0]["ticker"]))
    return merged


_ROOT_READ_ONLY_MSG = "Root is a combined view. Pick an account to add holdings to."


def resolve_write_owner():
    """Resolve which account a create/write should target, and authorize it.

    Returns (owner_id, current_user, error_response). Private users can only
    write to their own portfolio; the root user may target any account by
    passing its numeric id as the view.
    """
    current = get_current_user()
    if not current:
        return None, None, (jsonify({"error": "Authentication required"}), 401)
    view = (request.args.get("view") or "").lower()
    if current.role == "root" and view.isdigit():
        target = db.session.get(User, int(view))
        if not target:
            return None, None, (jsonify({"error": "Account not found"}), 404)
        if target.role == "root":
            return None, None, (jsonify({"error": _ROOT_READ_ONLY_MSG}), 400)
        return target.id, current, None
    if current.role == "root":
        return None, None, (jsonify({"error": _ROOT_READ_ONLY_MSG}), 400)
    return current.id, current, None


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


@app.route("/api/users/<int:user_id>", methods=["DELETE"])
@root_required
def delete_user(user_id):
    user = db.session.get(User, user_id)
    if not user:
        return jsonify({"error": "Account not found"}), 404
    if user.role != "private":
        return jsonify({"error": "Only private accounts can be deleted"}), 400

    # owner_id has no ON DELETE CASCADE, so remove the account's data explicitly.
    removed = {}
    for Model, key in ((Stock, "stocks"), (Option, "options"), (Property, "properties"), (PortfolioSnapshot, "snapshots")):
        removed[key] = Model.query.filter_by(owner_id=user.id).delete(synchronize_session=False)
    db.session.delete(user)
    db.session.commit()
    return jsonify({"message": f'Deleted account "{user.username}"', "removed": removed}), 200


# ---------------------------------------------------------------------------
# Portfolio summary
# ---------------------------------------------------------------------------

@app.route("/api/portfolio", methods=["GET"])
def get_portfolio():
    scope, masked, _ = resolve_view()
    stocks = _holdings(Stock, scope).all()
    properties = _holdings(Property, scope).all()
    options = _holdings(Option, scope).all()

    total_stock_value = sum(s.shares * (s.current_price or 0) for s in stocks)
    total_property_equity = sum((p.estimated_value or 0) - (p.mortgage_amount or 0) for p in properties)
    total_options_value = sum(o.market_value for o in options)

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
        "stock_count": len(_merge_stocks(stocks, masked)) if scope is None else len(stocks),
        "property_count": len(properties),
        "option_count": len({_option_key(o) for o in options}) if scope is None else len(options),
        "market_open": is_market_open(),
    })


# ---------------------------------------------------------------------------
# Portfolio history
# ---------------------------------------------------------------------------

@app.route("/api/portfolio/history", methods=["GET"])
def get_portfolio_history():
    scope, masked, _ = resolve_view()
    period = request.args.get("period", "1M")
    period_map = {"1D": 1, "1W": 7, "1M": 30, "3M": 90, "1Y": 365, "2Y": 730, "3Y": 1095, "5Y": 1825, "10Y": 3650, "ALL": None}
    days = period_map.get(period, 30)

    # History reveals dollar values over time, so it is hidden entirely when masked.
    if masked:
        return jsonify({"period": period, "masked": True, "snapshots": []})

    S = PortfolioSnapshot
    if scope is None:
        # Every account is snapshotted in the same pass, so summing rows that
        # share a timestamp gives the combined portfolio at that moment.
        query = db.session.query(
            S.timestamp.label("timestamp"),
            func.sum(S.total_value).label("total_value"),
            func.sum(S.stock_value).label("stock_value"),
            func.sum(S.property_equity).label("property_equity"),
            func.sum(func.coalesce(S.options_value, 0)).label("options_value"),
        ).group_by(S.timestamp)
    else:
        query = S.query.filter_by(owner_id=scope)
    query = query.order_by(S.timestamp.asc())
    if days is not None:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        query = query.filter(S.timestamp >= cutoff)

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
    scope, masked, _ = resolve_view()
    stocks = _holdings(Stock, scope).order_by(Stock.ticker).all()

    def _group(category):
        return "individual" if (category or "individual").lower() == "individual" else "other"

    if scope is None:
        rows = _merge_stocks(stocks, masked)
    else:
        rows = [(s.to_dict(masked=masked), _row_value(s)) for s in stocks]

    # Group totals mirror the frontend grouping: individual vs (diversified + cash).
    group_totals = {}
    for d, v in rows:
        group = _group(d["category"])
        group_totals[group] = group_totals.get(group, 0) + v

    properties = _holdings(Property, scope).all()
    options = _holdings(Option, scope).all()
    portfolio_total = (
        sum(v for _, v in rows)
        + sum((p.estimated_value or 0) - (p.mortgage_amount or 0) for p in properties)
        + sum(o.market_value for o in options)
    )

    result = []
    for d, v in rows:
        gt = group_totals.get(_group(d["category"]), 0)
        d["pct_of_group"] = round(v / gt * 100, 2) if gt else 0
        d["pct_of_portfolio"] = round(v / portfolio_total * 100, 2) if portfolio_total else 0
        result.append(d)

    return jsonify({
        "stocks": result,
        "masked": masked,
        "market_open": is_market_open(),
    })


@app.route("/api/stocks", methods=["POST"])
def add_stock():
    owner_id, _, err = resolve_write_owner()
    if err:
        return err
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
    """Fetch a row the authenticated user may modify, or an error response.

    A private user may only modify their own rows; the root user may modify
    any account's rows.
    """
    user = get_current_user()
    if not user:
        return None, (jsonify({"error": "Authentication required"}), 401)
    obj = db.session.get(model, obj_id)
    if not obj:
        return None, (jsonify({"error": "Not found"}), 404)
    if user.role != "root" and obj.owner_id != user.id:
        return None, (jsonify({"error": "You can only modify your own portfolio"}), 403)
    root = get_root_user()
    if root and obj.owner_id == root.id:
        return None, (jsonify({"error": _ROOT_READ_ONLY_MSG}), 403)
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
    scope, masked, _ = resolve_view()
    options = _holdings(Option, scope).order_by(
        Option.underlying_ticker, Option.expiration
    ).all()

    stocks = _holdings(Stock, scope).all()
    properties = _holdings(Property, scope).all()
    portfolio_total = (
        sum(s.shares * (s.current_price or 0) for s in stocks)
        + sum((p.estimated_value or 0) - (p.mortgage_amount or 0) for p in properties)
        + sum(o.market_value for o in options)
    )

    if scope is None:
        rows = _merge_rows(options, _option_key, "contracts", masked)
    else:
        rows = [(o.to_dict(masked=masked), o.market_value) for o in options]

    result = []
    for d, mv in rows:
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
def add_option():
    owner_id, _, err = resolve_write_owner()
    if err:
        return err
    data = request.get_json()
    ticker = (data.get("underlying_ticker") or data.get("ticker") or "").strip().upper()
    option_type = (data.get("option_type") or "call").lower()
    if option_type not in ("call", "put"):
        option_type = "call"
    expiration = (data.get("expiration") or "").strip()
    position = (data.get("position") or "bto").lower()
    if position not in ("bto", "sto"):
        return jsonify({"error": "Position must be BTO or STO"}), 400
    try:
        strike = float(data.get("strike", 0))
        contracts = int(data.get("contracts", 0))
    except (ValueError, TypeError):
        return jsonify({"error": "Invalid strike or contracts"}), 400

    if not ticker or not expiration or strike <= 0 or contracts <= 0:
        return jsonify({"error": "Ticker, expiration, positive strike, and positive contracts are required"}), 400

    info = fetch_option_data(ticker, expiration, strike, option_type)

    option = Option(
        owner_id=owner_id,
        underlying_ticker=ticker,
        underlying_name=info.get("underlying_name", ticker),
        option_type=option_type,
        strike=strike,
        expiration=expiration,
        contracts=contracts,
        position=position,
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
            contracts = int(data["contracts"])
        except (ValueError, TypeError):
            return jsonify({"error": "Invalid contracts"}), 400
        if contracts <= 0:
            return jsonify({"error": "Contracts must be positive"}), 400
        option.contracts = contracts
    if "position" in data:
        position = (data["position"] or "").lower()
        if position not in ("bto", "sto"):
            return jsonify({"error": "Position must be BTO or STO"}), 400
        option.position = position

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
    scope, masked, _ = resolve_view()
    properties = _holdings(Property, scope).order_by(Property.address).all()

    stocks = _holdings(Stock, scope).all()
    options = _holdings(Option, scope).all()
    portfolio_total = (
        sum(s.shares * (s.current_price or 0) for s in stocks)
        + sum((p.estimated_value or 0) - (p.mortgage_amount or 0) for p in properties)
        + sum(o.market_value for o in options)
    )

    result = []
    for p in properties:
        d = p.to_dict(masked=masked)
        equity = (p.estimated_value or 0) - (p.mortgage_amount or 0)
        d["pct_of_portfolio"] = round(equity / portfolio_total * 100, 2) if portfolio_total else 0
        result.append(d)

    return jsonify({"properties": result, "masked": masked})


_REDFIN_BLOCKED_MSG = (
    "Redfin is temporarily blocking automated lookups from this network. "
    "Wait 15-30 minutes and try again."
)


def _lookup_redfin_url(url):
    """Return (redfin_data, error_response)."""
    try:
        redfin_data = get_property_data_from_url(url)
    except RedfinBlockedError:
        return None, (jsonify({"error": _REDFIN_BLOCKED_MSG}), 503)
    except Exception as e:
        return None, (jsonify({"error": f"Failed to look up Redfin listing: {e}"}), 502)
    if not redfin_data or not redfin_data.get("estimated_value"):
        return None, (jsonify({
            "error": "Redfin has no estimate or last sold price for that link"
        }), 422)
    return redfin_data, None


def _apply_redfin_data(prop, redfin_data):
    prop.estimated_value = redfin_data["estimated_value"]
    prop.redfin_estimate = redfin_data.get("redfin_estimate") or 0
    prop.last_sold_price = redfin_data.get("last_sold_price") or 0
    prop.value_source = redfin_data.get("value_source") or ""
    if redfin_data.get("redfin_url"):
        prop.redfin_url = redfin_data["redfin_url"]
    if redfin_data.get("address"):
        prop.address = redfin_data["address"]
    if redfin_data.get("beds"):
        prop.beds = redfin_data["beds"]
    if redfin_data.get("baths"):
        prop.baths = redfin_data["baths"]
    if redfin_data.get("sqft"):
        prop.sqft = redfin_data["sqft"]


@app.route("/api/properties", methods=["POST"])
def add_property():
    owner_id, _, err = resolve_write_owner()
    if err:
        return err
    data = request.get_json() or {}
    redfin_url = (data.get("redfin_url") or "").strip()
    try:
        mortgage_amount = float(data.get("mortgage_amount") or 0)
    except (ValueError, TypeError):
        return jsonify({"error": "Mortgage amount must be a number"}), 400

    if not redfin_url:
        return jsonify({"error": "Redfin link is required"}), 400
    if "redfin.com" not in redfin_url.lower():
        return jsonify({"error": "Please paste a valid Redfin property link"}), 400

    redfin_data, err = _lookup_redfin_url(redfin_url)
    if err:
        return err

    prop = Property(owner_id=owner_id, address="Property", mortgage_amount=mortgage_amount)
    _apply_redfin_data(prop, redfin_data)
    prop.last_updated = datetime.now(timezone.utc)
    db.session.add(prop)
    db.session.commit()
    return jsonify(prop.to_dict()), 201


@app.route("/api/properties/<int:prop_id>", methods=["PUT"])
def update_property(prop_id):
    prop, err = _get_owned_or_error(Property, prop_id)
    if err:
        return err
    data = request.get_json() or {}

    if "mortgage_amount" in data:
        try:
            prop.mortgage_amount = float(data["mortgage_amount"] or 0)
        except (ValueError, TypeError):
            return jsonify({"error": "Mortgage amount must be a number"}), 400

    new_url = (data.get("redfin_url") or "").strip()
    if new_url and new_url != (prop.redfin_url or ""):
        if "redfin.com" not in new_url.lower():
            return jsonify({"error": "Please paste a valid Redfin property link"}), 400
        redfin_data, err = _lookup_redfin_url(new_url)
        if err:
            db.session.rollback()
            return err
        _apply_redfin_data(prop, redfin_data)

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

    try:
        if prop.redfin_url:
            details = scrape_redfin_estimate(prop.redfin_url)
        else:
            details = get_property_data(prop.address)
            if not details:
                return jsonify({"error": "Could not find property on Redfin"}), 404
    except RedfinBlockedError:
        return jsonify({"error": _REDFIN_BLOCKED_MSG + " Your saved value was kept."}), 503

    if not details or not details.get("estimated_value"):
        return jsonify({
            "error": "Redfin returned no estimate or last sold price. Your saved value was kept."
        }), 422
    _apply_redfin_data(prop, details)
    prop.last_updated = datetime.now(timezone.utc)
    db.session.commit()
    return jsonify(prop.to_dict())


if __name__ == "__main__":
    app.run(debug=True, port=5001)
