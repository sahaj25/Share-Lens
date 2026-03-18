from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from datetime import datetime

from database.queries import db_queries
from database.models import create_tables

app = FastAPI(title="Trading Tool API", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://sharelens.vercel.app", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Startup
@app.on_event("startup")
async def startup():
    create_tables()
    print("✅ Trading Tool API started")


# ─────────────────────────────────────────
# Health Check (FIXED)
# ─────────────────────────────────────────
@app.get("/")
async def root():
    return {"status": "ok"}   # ✅ simplified for uptime robot


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
async def get_signals(trade_type: str = None, limit: int = 50):
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

        return {
            "status": "success",
            "message": f"Position opened for {request.symbol}"
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class ClosePositionRequest(BaseModel):
    symbol: str
    exit_price: float
    exit_reason: str


@app.post("/positions/close")
async def close_position(request: ClosePositionRequest):
    try:
        db_queries.close_position(
            symbol=request.symbol,
            exit_price=request.exit_price,
            exit_reason=request.exit_reason
        )

        return {
            "status": "success",
            "message": f"Position closed for {request.symbol}"
        }

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
            return {
                "status": "success",
                "message": "No closed trades yet",
                "data": None
            }

        return {
            "status": "success",
            "data": summary
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))