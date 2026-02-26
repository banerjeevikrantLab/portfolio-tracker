from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone

db = SQLAlchemy()


class Stock(db.Model):
    __tablename__ = "stocks"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ticker = db.Column(db.String(10), nullable=False)
    company_name = db.Column(db.String(200), default="")
    shares = db.Column(db.Float, nullable=False)
    avg_cost = db.Column(db.Float, nullable=False)
    current_price = db.Column(db.Float, default=0.0)
    last_updated = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self):
        market_value = self.shares * (self.current_price or 0)
        cost_basis = self.shares * self.avg_cost
        gain_loss = market_value - cost_basis
        gain_loss_pct = (gain_loss / cost_basis * 100) if cost_basis else 0
        return {
            "id": self.id,
            "ticker": self.ticker,
            "company_name": self.company_name,
            "shares": self.shares,
            "avg_cost": self.avg_cost,
            "current_price": self.current_price,
            "market_value": round(market_value, 2),
            "cost_basis": round(cost_basis, 2),
            "gain_loss": round(gain_loss, 2),
            "gain_loss_pct": round(gain_loss_pct, 2),
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
        }


class Property(db.Model):
    __tablename__ = "properties"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    address = db.Column(db.String(500), nullable=False)
    redfin_url = db.Column(db.String(1000), default="")
    purchase_price = db.Column(db.Float, nullable=False, default=0.0)
    estimated_value = db.Column(db.Float, default=0.0)
    beds = db.Column(db.Float, default=0)
    baths = db.Column(db.Float, default=0)
    sqft = db.Column(db.Integer, default=0)
    last_updated = db.Column(
        db.DateTime, default=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self):
        gain_loss = (self.estimated_value or 0) - (self.purchase_price or 0)
        gain_loss_pct = (
            (gain_loss / self.purchase_price * 100) if self.purchase_price else 0
        )
        return {
            "id": self.id,
            "address": self.address,
            "redfin_url": self.redfin_url,
            "purchase_price": self.purchase_price,
            "estimated_value": self.estimated_value,
            "beds": self.beds,
            "baths": self.baths,
            "sqft": self.sqft,
            "gain_loss": round(gain_loss, 2),
            "gain_loss_pct": round(gain_loss_pct, 2),
            "last_updated": self.last_updated.isoformat() if self.last_updated else None,
        }
