from __future__ import annotations

import asyncio

import pandas as pd

from .crawler import BitcoinCrawler
from .decision import make_decision
from .model import BitcoinForecaster


class AnalysisService:
    def __init__(self) -> None:
        self.crawler = BitcoinCrawler()
        self.forecaster = BitcoinForecaster()
        self.lock = asyncio.Lock()

    async def history(self, days: int, force_refresh: bool = False) -> tuple[pd.DataFrame, str]:
        async with self.lock:
            return await self.crawler.get(days=days, force_refresh=force_refresh)

    async def analyze(self, horizon: int, history_days: int, force_refresh: bool = False) -> dict:
        frame, source = await self.history(history_days, force_refresh)
        forecast = await asyncio.to_thread(self.forecaster.forecast, frame, horizon)
        decision = make_decision(forecast, horizon)
        history = [
            {"date": row.date.date().isoformat(), "price": round(float(row.close), 2)}
            for row in frame.tail(180).itertuples()
        ]
        return {
            "as_of": frame.iloc[-1]["date"].date().isoformat(),
            "data_source": source,
            "horizon_days": horizon,
            "current_price": round(forecast.current_price, 2),
            "predicted_price": forecast.predicted_price,
            "expected_return_pct": round(forecast.expected_return_pct, 2),
            "forecast_range": {"lower": forecast.lower_price, "upper": forecast.upper_price},
            "history": history,
            "forecast": forecast.points,
            "metrics": {key: round(value, 2) if isinstance(value, float) else value for key, value in forecast.metrics.items()},
            "indicators": {key: round(value, 4) for key, value in forecast.latest_features.items()},
            "decision": decision,
        }


service = AnalysisService()

