import numpy as np
import pandas as pd

from app.decision import make_decision
from app.model import BitcoinForecaster


def synthetic_market(days: int = 420) -> pd.DataFrame:
    rng = np.random.default_rng(7)
    returns = rng.normal(0.001, 0.018, days)
    close = 30000 * np.exp(np.cumsum(returns))
    dates = pd.date_range("2024-01-01", periods=days, freq="D")
    return pd.DataFrame({
        "date": dates,
        "open": close * 0.997,
        "high": close * 1.015,
        "low": close * 0.985,
        "close": close,
        "volumefrom": rng.uniform(1000, 5000, days),
        "volumeto": rng.uniform(1e8, 8e8, days),
    })


def test_forecast_and_decision_have_valid_shapes():
    result = BitcoinForecaster().forecast(synthetic_market(), horizon=7)
    decision = make_decision(result, horizon=7)

    assert len(result.points) == 7
    assert result.current_price > 0
    assert all(point["lower"] < point["upper"] for point in result.points)
    assert decision["action"] in {"BUY", "HOLD", "SELL"}
    assert -100 <= decision["score"] <= 100

