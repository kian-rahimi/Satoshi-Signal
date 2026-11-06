from __future__ import annotations

import math

import numpy as np

from .model import ForecastResult


def make_decision(forecast: ForecastResult, horizon: int) -> dict:
    features = forecast.latest_features
    annualized_volatility = features["daily_volatility_30"] * math.sqrt(365)
    horizon_volatility_pct = features["daily_volatility_30"] * math.sqrt(horizon) * 100
    expected = forecast.expected_return_pct
    lower_return = (forecast.lower_price / forecast.current_price - 1) * 100
    upper_return = (forecast.upper_price / forecast.current_price - 1) * 100

    risk_adjusted_move = expected / max(horizon_volatility_pct, 1.0)
    forecast_score = float(np.clip(risk_adjusted_move, -1.5, 1.5) / 1.5 * 50)
    trend_score = float(np.clip((features["above_ma7_pct"] + features["above_ma30_pct"]) * 1.6, -22, 22))

    rsi = features["rsi_14"]
    if rsi >= 75:
        momentum_score = -12.0
    elif rsi <= 25:
        momentum_score = 8.0
    else:
        momentum_score = float(np.clip((rsi - 50) / 3, -8, 8))

    confidence_score = 10.0 if lower_return > 0 else (-10.0 if upper_return < 0 else 0.0)
    score = float(np.clip(forecast_score + trend_score + momentum_score + confidence_score, -100, 100))

    material_move = max(1.5, horizon_volatility_pct * 0.2)
    if score >= 25 and expected > material_move:
        action, emoji = "BUY", "🚀"
    elif score <= -25 and expected < -material_move:
        action, emoji = "SELL", "🪂"
    else:
        action, emoji = "HOLD", "🧘"

    if annualized_volatility >= 0.8:
        risk_level = "very high"
    elif annualized_volatility >= 0.55:
        risk_level = "high"
    elif annualized_volatility >= 0.35:
        risk_level = "medium"
    else:
        risk_level = "lower"

    reasons = [
        f"The {horizon}-day model implies {expected:+.2f}% from today's close.",
        f"Price is {features['above_ma30_pct']:+.2f}% versus its 30-day average.",
        f"RSI(14) is {rsi:.1f}; momentum is {'hot' if rsi > 70 else 'weak' if rsi < 30 else 'balanced'}.",
        f"The 90% forecast range spans {lower_return:+.2f}% to {upper_return:+.2f}%.",
    ]

    return {
        "action": action,
        "emoji": emoji,
        "score": round(score, 1),
        "confidence_pct": round(min(90.0, 45 + abs(score) * 0.45), 1),
        "risk_level": risk_level,
        "annualized_volatility_pct": round(annualized_volatility * 100, 1),
        "reasons": reasons,
        "disclaimer": "Educational decision support only—not financial advice. Crypto can lose substantial value. Validate assumptions and consult a qualified adviser before trading.",
    }

