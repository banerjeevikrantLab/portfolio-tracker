from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone

db = SQLAlchemy()


STOCK_CATEGORIES = ("individual", "diversified", "cash_equivalent")


class Stock(db.Model):
    __tablename__ = "stocks"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ticker = db.Column(db.String(10), nullable=False)
    company_name = db.Column(db.String(200), default="")
    shares = db.Column(db.Float, nullable=False)
    category = db.Column(db.String(30), default="individual")  # individual, diversified, cash_equivalent
    avg_cost = db.Column(db.Float, nullable=True, default=0)  # kept for DB compat, not displayed
    current_price = db.Column(db.Float, default=0.0)
    last_updated = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self):
        market_value = self.shares * (self.current_price or 0)
        return {
            "id": self.id,
            "ticker": self.ticker,
            "company_name": self.company_name,
            "shares": self.shares,
            "category": self.category or "individual",
            "current_price": self.current_price,
            "market_value": round(market_value, 2),
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
        }


class Property(db.Model):
    __tablename__ = "properties"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
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

    def to_dict(self):
        equity = (self.estimated_value or 0) - (self.mortgage_amount or 0)
        return {
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
