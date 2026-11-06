"""Direct multi-horizon time-series forecasting with walk-forward validation."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .features import FEATURE_COLUMNS, add_features


@dataclass
class ForecastResult:
    points: list[dict]
    metrics: dict
    current_price: float
    predicted_price: float
    lower_price: float
    upper_price: float
    expected_return_pct: float
    latest_features: dict


class StandardizedRidge:
    """Small NumPy Ridge regressor with standardized inputs and an intercept."""

    def __init__(self, alpha: float) -> None:
        self.alpha = alpha
        self.mean_: np.ndarray | None = None
        self.scale_: np.ndarray | None = None
        self.coef_: np.ndarray | None = None

    def fit(self, x: pd.DataFrame | np.ndarray, y: pd.Series | np.ndarray) -> "StandardizedRidge":
        matrix = np.asarray(x, dtype=float)
        target = np.asarray(y, dtype=float)
        self.mean_ = matrix.mean(axis=0)
        self.scale_ = matrix.std(axis=0)
        self.scale_[self.scale_ < 1e-12] = 1.0
        standardized = (matrix - self.mean_) / self.scale_
        design = np.column_stack([np.ones(len(standardized)), standardized])
        penalty = np.eye(design.shape[1]) * self.alpha
        penalty[0, 0] = 0.0
        self.coef_ = np.linalg.solve(design.T @ design + penalty, design.T @ target)
        return self

    def predict(self, x: pd.DataFrame | np.ndarray) -> np.ndarray:
        if self.mean_ is None or self.scale_ is None or self.coef_ is None:
            raise RuntimeError("Model must be fitted before prediction")
        matrix = np.asarray(x, dtype=float)
        design = np.column_stack([np.ones(len(matrix)), (matrix - self.mean_) / self.scale_])
        return design @ self.coef_


def mean_absolute_error(actual: np.ndarray | pd.Series, predicted: np.ndarray) -> float:
    return float(np.mean(np.abs(np.asarray(actual, dtype=float) - np.asarray(predicted, dtype=float))))


def time_series_splits(length: int, splits: int):
    """Yield expanding training windows followed by non-overlapping validation windows."""
    validation_size = max(1, length // (splits + 1))
    first_train_end = length - validation_size * splits
    for index in range(splits):
        train_end = first_train_end + index * validation_size
        validation_end = min(length, train_end + validation_size)
        yield np.arange(train_end), np.arange(train_end, validation_end)


class BitcoinForecaster:
    """Ridge autoregression blended with a robust drift model."""

    alphas = (0.1, 1.0, 10.0, 100.0)

    @staticmethod
    def _pipeline(alpha: float) -> StandardizedRidge:
        return StandardizedRidge(alpha)

    def _choose_alpha(self, x: pd.DataFrame, y: pd.Series) -> float:
        splits = min(5, max(2, len(x) // 100))
        best_alpha, best_mae = 10.0, float("inf")
        for alpha in self.alphas:
            errors: list[float] = []
            for train_idx, validation_idx in time_series_splits(len(x), splits):
                model = self._pipeline(alpha)
                model.fit(x.iloc[train_idx], y.iloc[train_idx])
                prediction = model.predict(x.iloc[validation_idx])
                errors.append(mean_absolute_error(y.iloc[validation_idx], prediction))
            score = float(np.mean(errors))
            if score < best_mae:
                best_alpha, best_mae = alpha, score
        return best_alpha

    def forecast(self, raw: pd.DataFrame, horizon: int = 14) -> ForecastResult:
        featured = add_features(raw)
        latest = featured.dropna(subset=FEATURE_COLUMNS).iloc[-1]
        latest_x = latest[FEATURE_COLUMNS].to_frame().T.astype(float)
        current_price = float(latest["close"])
        current_date = pd.Timestamp(latest["date"])

        one_day = featured.copy()
        one_day["target"] = np.log(one_day["close"].shift(-1) / one_day["close"])
        one_day = one_day.dropna(subset=FEATURE_COLUMNS + ["target"])
        if len(one_day) < 120:
            raise ValueError("At least 180 cleaned daily candles are required for forecasting")

        split_at = max(100, int(len(one_day) * 0.8))
        train, test = one_day.iloc[:split_at], one_day.iloc[split_at:]
        alpha = self._choose_alpha(train[FEATURE_COLUMNS], train["target"])
        evaluation_model = self._pipeline(alpha)
        evaluation_model.fit(train[FEATURE_COLUMNS], train["target"])
        test_prediction = evaluation_model.predict(test[FEATURE_COLUMNS])
        test_actual_price = test["close"].to_numpy() * np.exp(test["target"].to_numpy())
        test_predicted_price = test["close"].to_numpy() * np.exp(test_prediction)
        residuals = test["target"].to_numpy() - test_prediction
        residual_std = max(float(np.std(residuals)), 1e-6)

        metrics = {
            "model": "Ridge autoregression + robust drift ensemble",
            "validation_method": "expanding-window time-series split + held-out final 20%",
            "alpha": alpha,
            "mae_usd": float(mean_absolute_error(test_actual_price, test_predicted_price)),
            "mape_pct": float(np.mean(np.abs((test_actual_price - test_predicted_price) / test_actual_price)) * 100),
            "directional_accuracy_pct": float(np.mean(np.sign(test["target"]) == np.sign(test_prediction)) * 100),
            "test_samples": int(len(test)),
            "training_samples": int(len(one_day)),
        }

        recent_returns = featured["log_return"].dropna().tail(60)
        robust_daily_drift = float(recent_returns.clip(
            recent_returns.quantile(0.1), recent_returns.quantile(0.9)
        ).mean())

        points: list[dict] = []
        for step in range(1, horizon + 1):
            supervised = featured.copy()
            supervised["target"] = np.log(supervised["close"].shift(-step) / supervised["close"])
            supervised = supervised.dropna(subset=FEATURE_COLUMNS + ["target"])
            model = self._pipeline(alpha)
            model.fit(supervised[FEATURE_COLUMNS], supervised["target"])
            ridge_return = float(model.predict(latest_x)[0])
            drift_return = robust_daily_drift * step
            # A conservative ensemble reduces the tendency of direct models to overreact.
            predicted_return = 0.75 * ridge_return + 0.25 * drift_return
            uncertainty = 1.645 * residual_std * np.sqrt(step)
            price = current_price * np.exp(predicted_return)
            lower = current_price * np.exp(predicted_return - uncertainty)
            upper = current_price * np.exp(predicted_return + uncertainty)
            points.append({
                "date": (current_date + pd.Timedelta(days=step)).date().isoformat(),
                "price": round(float(price), 2),
                "lower": round(float(lower), 2),
                "upper": round(float(upper), 2),
            })

        last = points[-1]
        return ForecastResult(
            points=points,
            metrics=metrics,
            current_price=current_price,
            predicted_price=last["price"],
            lower_price=last["lower"],
            upper_price=last["upper"],
            expected_return_pct=(last["price"] / current_price - 1) * 100,
            latest_features={
                "rsi_14": float(latest["rsi_14"]),
                "momentum_7": float(latest["momentum_7"]),
                "momentum_30": float(latest["momentum_30"]),
                "daily_volatility_30": float(latest["volatility_30"]),
                "above_ma7_pct": float(latest["price_ma7_ratio"] * 100),
                "above_ma30_pct": float(latest["price_ma30_ratio"] * 100),
            },
        )

