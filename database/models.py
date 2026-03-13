from sqlalchemy import (
    create_engine, Column, Integer, Float,
    String, Boolean, DateTime, Text
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
from config import DATABASE_URL

Base = declarative_base()


# ─────────────────────────────────────────
# Signals Table — every signal generated
# ─────────────────────────────────────────
class Signal(Base):
    __tablename__ = "signals"

    id = Column(Integer, primary_key=True)
    symbol = Column(String(20), nullable=False)
    signal_type = Column(String(10))  # BUY / SELL
    trade_type = Column(String(10))  # SWING / INTRADAY
    score = Column(Float)
    entry = Column(Float)
    stop_loss = Column(Float)
    target = Column(Float)
    risk_reward = Column(Float)
    confidence = Column(String(20))
    reasoning = Column(Text)
    caution = Column(Text)
    rsi = Column(Float)
    adx = Column(Float)
    volume_ratio = Column(Float)
    created_at = Column(DateTime, default=datetime.now)

    def __repr__(self):
        return f"<Signal {self.symbol} {self.signal_type} {self.score}>"


# ─────────────────────────────────────────
# Positions Table — trades you actually take
# ─────────────────────────────────────────
class Position(Base):
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True)
    symbol = Column(String(20), nullable=False)
    signal = Column(String(10))  # BUY / SELL
    trade_type = Column(String(10))  # SWING / INTRADAY
    entry = Column(Float)
    stop_loss = Column(Float)
    target = Column(Float)
    quantity = Column(Integer)
    capital_used = Column(Float)
    current_price = Column(Float)
    unrealised_pnl = Column(Float, default=0)
    pnl_pct = Column(Float, default=0)
    exit_price = Column(Float, nullable=True)
    exit_reason = Column(String(20), nullable=True)  # TARGET_HIT / SL_HIT / MANUAL
    is_open = Column(Boolean, default=True)
    opened_at = Column(DateTime, default=datetime.now)
    closed_at = Column(DateTime, nullable=True)

    def __repr__(self):
        return f"<Position {self.symbol} {self.signal} open={self.is_open}>"


# ─────────────────────────────────────────
# Performance Table — daily P&L tracking
# ─────────────────────────────────────────
class DailyPerformance(Base):
    __tablename__ = "daily_performance"

    id = Column(Integer, primary_key=True)
    date = Column(String(20), nullable=False)
    total_trades = Column(Integer, default=0)
    winning_trades = Column(Integer, default=0)
    losing_trades = Column(Integer, default=0)
    total_pnl = Column(Float, default=0)
    win_rate = Column(Float, default=0)
    best_trade = Column(String(20), nullable=True)
    worst_trade = Column(String(20), nullable=True)
    market_mood = Column(String(20), nullable=True)
    created_at = Column(DateTime, default=datetime.now)

    def __repr__(self):
        return f"<DailyPerformance {self.date} PnL={self.total_pnl}>"


# ─────────────────────────────────────────
# Database setup
# ─────────────────────────────────────────
engine = create_engine(DATABASE_URL,     connect_args={"check_same_thread": False}     if "sqlite" in DATABASE_URL else {} )
SessionLocal = sessionmaker(bind=engine)


def create_tables():
    """Create all tables if they don't exist"""
    Base.metadata.create_all(engine)
    print("✅ Database tables created")


def get_db():
    """Get database session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()