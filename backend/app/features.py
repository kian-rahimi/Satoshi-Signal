from __future__ import annotations

import numpy as np
import pandas as pd


FEATURE_COLUMNS = [
    *(f"return_lag_{lag}" for lag in range(1, 15)),
    "price_ma7_ratio",
    "price_ma30_ratio",
    "momentum_7",
    "momentum_30",
    "volatility_14",
    "volatility_30",
    "rsi_14",
    "volume_zscore",
]


def add_features(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame.copy().sort_values("date").reset_index(drop=True)
    close = data["close"].astype(float)
    returns = np.log(close).diff()
    data["log_return"] = returns
    for lag in range(1, 15):
        data[f"return_lag_{lag}"] = returns.shift(lag)

    data["price_ma7_ratio"] = close / close.rolling(7).mean() - 1
    data["price_ma30_ratio"] = close / close.rolling(30).mean() - 1
    data["momentum_7"] = close.pct_change(7)
    data["momentum_30"] = close.pct_change(30)
    data["volatility_14"] = returns.rolling(14).std()
    data["volatility_30"] = returns.rolling(30).std()

    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / 14, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / 14, adjust=False).mean()
    relative_strength = gain / loss.replace(0, np.nan)
    data["rsi_14"] = (100 - (100 / (1 + relative_strength))).fillna(50)

    volume = np.log1p(data["volumeto"].astype(float))
    data["volume_zscore"] = (
        (volume - volume.rolling(30).mean()) / volume.rolling(30).std().replace(0, np.nan)
    )
    return data.replace([np.inf, -np.inf], np.nan)

