"""Fetch and clean daily BTC/USD OHLCV data from CryptoCompare."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import httpx
import numpy as np
import pandas as pd

from .config import settings


class MarketDataError(RuntimeError):
    """Raised when usable market data cannot be retrieved."""


class BitcoinCrawler:
    cryptocompare_endpoint = "https://min-api.cryptocompare.com/data/v2/histoday"
    yahoo_endpoint = "https://query1.finance.yahoo.com/v8/finance/chart/BTC-USD"

    def __init__(self, cache_file: Path | None = None) -> None:
        self.cache_file = cache_file or settings.cache_file

    async def fetch(self, days: int = 900) -> pd.DataFrame:
        """Fetch daily candles and return cleaned data.

        Yahoo Finance is keyless. When a CryptoCompare key is configured, that
        provider is used instead as an optional alternative source.
        """
        if settings.cryptocompare_api_key:
            return await self._fetch_cryptocompare(days)
        return await self._fetch_yahoo(days)

    async def _fetch_cryptocompare(self, days: int) -> pd.DataFrame:
        params: dict[str, str | int] = {
            "fsym": "BTC",
            "tsym": "USD",
            "limit": min(days - 1, 2000),
            "aggregate": 1,
        }
        headers = {"User-Agent": "Satoshis-Crystal-Ball/1.0"}
        if settings.cryptocompare_api_key:
            headers["authorization"] = f"Apikey {settings.cryptocompare_api_key}"

        try:
            async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
                response = await client.get(self.cryptocompare_endpoint, params=params, headers=headers)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise MarketDataError(f"Market data request failed: {exc}") from exc

        if payload.get("Response") == "Error":
            raise MarketDataError(payload.get("Message", "CryptoCompare returned an error"))

        rows = payload.get("Data", {}).get("Data", [])
        if not rows:
            raise MarketDataError("The market data provider returned no candles")
        return self.clean(pd.DataFrame(rows)).tail(days).reset_index(drop=True)

    async def _fetch_yahoo(self, days: int) -> pd.DataFrame:
        range_value = "10y" if days > 1800 else ("5y" if days > 365 else "1y")
        params = {"range": range_value, "interval": "1d", "events": "history"}
        headers = {"User-Agent": "Satoshis-Crystal-Ball/1.0"}
        try:
            async with httpx.AsyncClient(timeout=settings.request_timeout_seconds) as client:
                response = await client.get(self.yahoo_endpoint, params=params, headers=headers)
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise MarketDataError(f"Yahoo Finance market data request failed: {exc}") from exc

        chart = payload.get("chart", {})
        if chart.get("error"):
            raise MarketDataError(f"Yahoo Finance returned: {chart['error']}")
        results = chart.get("result") or []
        if not results:
            raise MarketDataError("Yahoo Finance returned no BTC/USD chart")
        result = results[0]
        timestamps = result.get("timestamp") or []
        quote = ((result.get("indicators") or {}).get("quote") or [{}])[0]
        if not timestamps or not quote.get("close"):
            raise MarketDataError("Yahoo Finance returned no BTC/USD candles")

        normalized = pd.DataFrame({"time": timestamps, **quote})
        normalized["volumeto"] = pd.to_numeric(normalized["volume"], errors="coerce")
        normalized["volumefrom"] = normalized["volumeto"] / pd.to_numeric(
            normalized["close"], errors="coerce"
        ).replace(0, np.nan)
        return self.clean(normalized).tail(days).reset_index(drop=True)

    @staticmethod
    def clean(raw: pd.DataFrame) -> pd.DataFrame:
        """Normalize types, fill missing days, and remove invalid observations."""
        required = ["time", "open", "high", "low", "close", "volumefrom", "volumeto"]
        missing = [column for column in required if column not in raw.columns]
        if missing:
            raise MarketDataError(f"Missing columns: {', '.join(missing)}")

        frame = raw[required].copy()
        frame["date"] = pd.to_datetime(frame.pop("time"), unit="s", utc=True).dt.tz_localize(None)
        numeric = ["open", "high", "low", "close", "volumefrom", "volumeto"]
        frame[numeric] = frame[numeric].apply(pd.to_numeric, errors="coerce")
        frame = frame.replace([np.inf, -np.inf], np.nan)
        frame = frame.drop_duplicates("date", keep="last").sort_values("date")
        frame = frame[frame["close"] > 0].set_index("date")

        if frame.empty:
            raise MarketDataError("All returned price rows were invalid")

        full_index = pd.date_range(frame.index.min(), frame.index.max(), freq="D")
        frame = frame.reindex(full_index)
        frame["close"] = frame["close"].interpolate(method="time").ffill().bfill()
        for column in ["open", "high", "low"]:
            frame[column] = frame[column].fillna(frame["close"])
        for column in ["volumefrom", "volumeto"]:
            frame[column] = frame[column].fillna(0).clip(lower=0)
            upper = frame[column].quantile(0.995)
            if upper > 0:
                frame[column] = frame[column].clip(upper=upper)

        # Restore valid candle geometry after interpolation.
        frame["high"] = frame[["open", "high", "close"]].max(axis=1)
        frame["low"] = frame[["open", "low", "close"]].min(axis=1)
        frame.index.name = "date"
        return frame.reset_index()

    def save(self, frame: pd.DataFrame) -> None:
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(self.cache_file, index=False)

    def load_cache(self, days: int) -> pd.DataFrame | None:
        if not self.cache_file.exists():
            return None
        age_seconds = datetime.now(timezone.utc).timestamp() - self.cache_file.stat().st_mtime
        if age_seconds > settings.cache_ttl_minutes * 60:
            return None
        try:
            frame = pd.read_csv(self.cache_file, parse_dates=["date"])
            return self.clean_cached(frame).tail(days).reset_index(drop=True)
        except (OSError, ValueError, KeyError):
            return None

    @staticmethod
    def clean_cached(frame: pd.DataFrame) -> pd.DataFrame:
        expected = {"date", "open", "high", "low", "close", "volumefrom", "volumeto"}
        if not expected.issubset(frame.columns):
            raise MarketDataError("Cached file has an invalid schema")
        frame = frame.copy()
        frame["date"] = pd.to_datetime(frame["date"], errors="raise")
        return frame.sort_values("date").drop_duplicates("date", keep="last")

    async def get(self, days: int = 900, force_refresh: bool = False) -> tuple[pd.DataFrame, str]:
        if not force_refresh:
            cached = self.load_cache(days)
            if cached is not None and len(cached) >= min(days, 180):
                return cached, "cache"
        try:
            fresh = await self.fetch(days)
            self.save(fresh)
            provider = "cryptocompare_web" if settings.cryptocompare_api_key else "yahoo_finance_web"
            return fresh, provider
        except MarketDataError:
            # Stale data is safer than a blank dashboard and is clearly labeled by the API.
            if self.cache_file.exists():
                stale = pd.read_csv(self.cache_file, parse_dates=["date"])
                return self.clean_cached(stale).tail(days).reset_index(drop=True), "stale_cache"
            raise

