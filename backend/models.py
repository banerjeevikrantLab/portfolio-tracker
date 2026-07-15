from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone

db = SQLAlchemy()


STOCK_CATEGORIES = ("individual", "diversified", "cash_equivalent")

USER_ROLES = ("root", "private")


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    username = db.Column(db.String(80), nullable=False, unique=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default="private")  # root, private
    created_at = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "role": self.role or "private",
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Stock(db.Model):
    __tablename__ = "stocks"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    ticker = db.Column(db.String(10), nullable=False)
    company_name = db.Column(db.String(200), default="")
    shares = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(30), default="individual")  # individual, diversified, cash_equivalent
    is_cash = db.Column(db.Boolean, default=False)  # plain cash entry (no ticker/price lookup)
    avg_cost = db.Column(db.Float, nullable=True, default=0)  # kept for DB compat, not displayed
    current_price = db.Column(db.Float, default=0.0)
    previous_close = db.Column(db.Float, default=0.0)
    dividend_yield = db.Column(db.Float, default=0.0)
    annual_dividend = db.Column(db.Float, default=0.0)
    week52_high = db.Column(db.Float, default=0.0)
    week52_low = db.Column(db.Float, default=0.0)
    last_updated = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self, masked=False):
        market_value = self.shares * (self.current_price or 0)
        prev = self.previous_close or 0
        cur = self.current_price or 0
        day_change = round(cur - prev, 2) if prev else 0
        day_change_pct = round(day_change / prev * 100, 2) if prev else 0
        data = {
            "id": self.id,
            "ticker": self.ticker,
            "company_name": self.company_name,
            "shares": self.shares,
            "category": self.category or "individual",
            "is_cash": bool(self.is_cash),
            "current_price": self.current_price,
            "previous_close": prev,
            "day_change": day_change,
            "day_change_pct": day_change_pct,
            "market_value": round(market_value, 2),
            "dividend_yield": self.dividend_yield or 0,
            "annual_dividend": self.annual_dividend or 0,
            "week52_high": self.week52_high or 0,
            "week52_low": self.week52_low or 0,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
        }
        if masked:
            for field in (
                "shares", "current_price", "previous_close", "day_change",
                "market_value", "annual_dividend", "week52_high", "week52_low",
            ):
                data[field] = None
        return data


class Option(db.Model):
    __tablename__ = "options"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    underlying_ticker = db.Column(db.String(10), nullable=False)
    underlying_name = db.Column(db.String(200), default="")
    option_type = db.Column(db.String(4), default="call")  # call, put
    strike = db.Column(db.Float, nullable=False)
    expiration = db.Column(db.String(10), nullable=False)  # YYYY-MM-DD
    contracts = db.Column(db.Integer, nullable=False, default=1)
    contract_symbol = db.Column(db.String(40), default="")  # OCC symbol
    current_price = db.Column(db.Float, default=0.0)  # per-share premium
    last_updated = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self, masked=False):
        # Standard equity option multiplier of 100 shares per contract
        market_value = (self.current_price or 0) * 100 * (self.contracts or 0)
        data = {
            "id": self.id,
            "underlying_ticker": self.underlying_ticker,
            "underlying_name": self.underlying_name,
            "option_type": self.option_type or "call",
            "strike": self.strike,
            "expiration": self.expiration,
            "contracts": self.contracts,
            "contract_symbol": self.contract_symbol,
            "current_price": self.current_price or 0,
            "market_value": round(market_value, 2),
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
        }
        if masked:
            for field in ("strike", "current_price", "market_value", "contracts"):
                data[field] = None
        return data


class Property(db.Model):
    __tablename__ = "properties"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    address = db.Column(db.String(500), nullable=False)
    redfin_url = db.Column(db.String(1000), default="")
    mortgage_amount = db.Column(db.Float, default=0.0)
    estimated_value = db.Column(db.Float, default=0.0)
    beds = db.Column(db.Float, default=0)
    baths = db.Column(db.Float, default=0)
    sqft = db.Column(db.Integer, default=0)
    last_updated = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self, masked=False):
        equity = (self.estimated_value or 0) - (self.mortgage_amount or 0)
        data = {
            "id": self.id,
            "address": self.address,
            "redfin_url": self.redfin_url,
            "mortgage_amount": self.mortgage_amount or 0,
            "estimated_value": self.estimated_value,
            "equity": round(equity, 2),
            "beds": self.beds,
            "baths": self.baths,
            "sqft": self.sqft,
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
        }
        if masked:
            data["address"] = None
            data["redfin_url"] = None
            for field in ("mortgage_amount", "estimated_value", "equity"):
                data[field] = None
        return data


class PortfolioSnapshot(db.Model):
    __tablename__ = "portfolio_snapshots"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    owner_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True, index=True)
    timestamp = db.Column(db.DateTime, nullable=False)
    total_value = db.Column(db.Float, default=0.0)
    stock_value = db.Column(db.Float, default=0.0)
    property_equity = db.Column(db.Float, default=0.0)
    options_value = db.Column(db.Float, default=0.0)
