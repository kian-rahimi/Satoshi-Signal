from __future__ import annotations

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .crawler import MarketDataError
from .service import service


app = FastAPI(
    title=settings.app_name,
    version="1.0.0",
    description="BTC/USD time-series forecasting and explainable decision support.",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "service": settings.app_name}


@app.get("/api/history")
async def history(days: int = Query(365, ge=180, le=2000)) -> dict:
    try:
        frame, source = await service.history(days)
        return {
            "data_source": source,
            "items": [
                {
                    "date": row.date.date().isoformat(),
                    "open": round(float(row.open), 2),
                    "high": round(float(row.high), 2),
                    "low": round(float(row.low), 2),
                    "close": round(float(row.close), 2),
                    "volume_usd": round(float(row.volumeto), 2),
                }
                for row in frame.itertuples()
            ],
        }
    except MarketDataError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@app.get("/api/analyze")
async def analyze(
    horizon: int = Query(14, ge=1, le=30),
    history_days: int = Query(900, ge=180, le=2000),
    refresh: bool = False,
) -> dict:
    try:
        return await service.analyze(horizon, history_days, refresh)
    except MarketDataError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/refresh")
async def refresh(
    horizon: int = Query(14, ge=1, le=30),
    history_days: int = Query(900, ge=180, le=2000),
) -> dict:
    return await analyze(horizon=horizon, history_days=history_days, refresh=True)

