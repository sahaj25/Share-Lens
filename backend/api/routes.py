from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, field_validator   # FIX: use field_validator (Pydantic V2)
from datetime import datetime

from database.queries import db_queries
from database.models import create_tables


# ─────────────────────────────────────────
# Lifespan
# ─────────────────────────────────────────
from scheduler.jobs import create_scheduler

scheduler = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global scheduler

    create_tables()
    print("✅ Trading Tool API started")

    # START scheduler here
    scheduler = create_scheduler()
    scheduler.start()
    print("✅ Scheduler started inside FastAPI")

    yield

    # STOP scheduler on shutdown
    if scheduler and scheduler.running:
        scheduler.shutdown(wait=False)
        print("⏱ Scheduler stopped")

app = FastAPI(
    title="Trading Tool API",
    version="1.0.0",
    lifespan=lifespan
)

# ─────────────────────────────────────────
# CORS
# ─────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://sharelens.vercel.app", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────
# Health Check
# ─────────────────────────────────────────
@app.api_route("/", methods=["GET", "HEAD"])
async def root(request: Request):
    return {"status": "ok"}


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    }


# ─────────────────────────────────────────
# Manual Trigger Endpoints
# ─────────────────────────────────────────
@app.post("/trigger/swing-scan")
async def trigger_swing_scan():
    try:
        from scheduler.jobs import job_swing_scan
        job_swing_scan()
        return {"status": "success", "message": "Swing scan triggered"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/trigger/intraday-scan")
async def trigger_intraday_scan():
    try:
        from scheduler.jobs import job_intraday_scan
        job_intraday_scan()
        return {"status": "success", "message": "Intraday scan triggered"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/trigger/eod-summary")
async def trigger_eod_summary():
    try:
        from scheduler.jobs import job_eod_summary
        job_eod_summary()
        return {"status": "success", "message": "EOD summary triggered"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────
# Signals
# ─────────────────────────────────────────
@app.get("/signals")
async def get_signals(
    trade_type: str = Query(default=None, description="SWING or INTRADAY"),
    limit: int = Query(default=50, ge=1, le=200)
):
    if trade_type and trade_type not in ("SWING", "INTRADAY"):
        raise HTTPException(status_code=400, detail="trade_type must be 'SWING' or 'INTRADAY'")

    try:
        signals = db_queries.get_all_signals(trade_type=trade_type, limit=limit)
        return {
            "status": "success",
            "count": len(signals),
            "signals": [
                {
                    "id": s.id,
                    "symbol": s.symbol,
                    "signal_type": s.signal_type,
                    "trade_type": s.trade_type,
                    "score": s.score,
                    "entry": s.entry,
                    "stop_loss": s.stop_loss,
                    "target": s.target,
                    "risk_reward": s.risk_reward,
                    "confidence": s.confidence,
                    "reasoning": s.reasoning,
                    "rsi": s.rsi,
                    "adx": s.adx,
                    "created_at": s.created_at.isoformat()
                }
                for s in signals
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────
# Positions
# ─────────────────────────────────────────
@app.get("/positions/open")
async def get_open_positions():
    try:
        positions = db_queries.get_open_positions()
        return {
            "status": "success",
            "count": len(positions),
            "positions": positions
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class OpenPositionRequest(BaseModel):
    symbol: str
    signal: str
    entry: float
    stop_loss: float
    target: float
    quantity: int
    capital_used: float
    trade_type: str

    # FIX: Pydantic V2 uses @field_validator instead of @validator
    # @validator with `field` param was removed in Pydantic V2
    @field_validator("signal")
    @classmethod
    def signal_must_be_valid(cls, v):
        if v not in ("BUY", "SELL"):
            raise ValueError("signal must be 'BUY' or 'SELL'")
        return v

    @field_validator("trade_type")
    @classmethod
    def trade_type_must_be_valid(cls, v):
        if v not in ("SWING", "INTRADAY"):
            raise ValueError("trade_type must be 'SWING' or 'INTRADAY'")
        return v

    @field_validator("entry", "stop_loss", "target", "capital_used")
    @classmethod
    def must_be_positive(cls, v):
        # FIX: removed `field` parameter — not available in Pydantic V2
        if v <= 0:
            raise ValueError("value must be greater than 0")
        return v

    @field_validator("quantity")
    @classmethod
    def quantity_must_be_positive(cls, v):
        if v < 1:
            raise ValueError("quantity must be at least 1")
        return v


@app.post("/positions/open")
async def open_position(request: OpenPositionRequest):
    try:
        signal_data = {
            "symbol": request.symbol,
            "signal": request.signal,
            "entry": request.entry,
            "stop_loss": request.stop_loss,
            "target": request.target
        }
        db_queries.open_position(
            signal_data=signal_data,
            quantity=request.quantity,
            capital_used=request.capital_used,
            trade_type=request.trade_type
        )
        return {"status": "success", "message": f"Position opened for {request.symbol}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ClosePositionRequest(BaseModel):
    symbol: str
    exit_price: float
    exit_reason: str

    @field_validator("exit_reason")
    @classmethod
    def exit_reason_must_be_valid(cls, v):
        if v not in ("TARGET_HIT", "SL_HIT", "MANUAL"):
            raise ValueError("exit_reason must be 'TARGET_HIT', 'SL_HIT', or 'MANUAL'")
        return v

    @field_validator("exit_price")
    @classmethod
    def exit_price_must_be_positive(cls, v):
        if v <= 0:
            raise ValueError("exit_price must be greater than 0")
        return v


@app.post("/positions/close")
async def close_position(request: ClosePositionRequest):
    try:
        db_queries.close_position(
            symbol=request.symbol,
            exit_price=request.exit_price,
            exit_reason=request.exit_reason
        )
        return {"status": "success", "message": f"Position closed for {request.symbol}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────
# Performance
# ─────────────────────────────────────────
@app.get("/performance")
async def get_performance():
    try:
        summary = db_queries.get_performance_summary()
        if not summary:
            return {"status": "success", "message": "No closed trades yet", "data": None}
        return {"status": "success", "data": summary}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─────────────────────────────────────────
# Closed Positions
# ─────────────────────────────────────────
@app.get("/positions/closed")
async def get_closed_positions(
    limit: int = Query(default=50, ge=1, le=200)
):
    try:
        from database.models import Position, SessionLocal
        db = SessionLocal()
        try:
            positions = (
                db.query(Position)
                .filter(Position.is_open == False)
                .order_by(Position.closed_at.desc())
                .limit(limit)
                .all()
            )
            return {
                "status": "success",
                "count": len(positions),
                "positions": [
                    {
                        "id": p.id,
                        "symbol": p.symbol,
                        "signal": p.signal,
                        "trade_type": p.trade_type,
                        "entry": p.entry,
                        "exit_price": p.exit_price,
                        "stop_loss": p.stop_loss,
                        "target": p.target,
                        "quantity": p.quantity,
                        "capital_used": p.capital_used,
                        "exit_reason": p.exit_reason,
                        "opened_at": p.opened_at.isoformat() if p.opened_at else None,
                        "closed_at": p.closed_at.isoformat() if p.closed_at else None,
                    }
                    for p in positions
                ]
            }
        finally:
            db.close()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))