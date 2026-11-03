"""Business forecasting with scikit-learn.

Approach: aggregate the chosen metric per month, fit a linear model with a
time index plus seasonal (month-of-year sine/cosine) features, and project
forward. Prediction intervals come from the residual standard deviation.
Falls back to a seasonal-naive forecast when there are too few points.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

from .analysis import pick_date_column, pick_primary_metric

MIN_POINTS = 4


def _seasonal_features(periods: pd.PeriodIndex) -> np.ndarray:
    t = np.arange(len(periods), dtype=float)
    months = np.array([p.month for p in periods], dtype=float)
    return np.column_stack([
        t,
        np.sin(2 * np.pi * months / 12.0),
        np.cos(2 * np.pi * months / 12.0),
    ])


def forecast_metric(df: pd.DataFrame, metric: str | None = None, periods: int = 6) -> dict[str, Any]:
    metric = metric or pick_primary_metric(df)
    date_col = pick_date_column(df)
    periods = int(max(1, min(periods, 24)))

    if not metric or not date_col:
        return {"available": False, "reason": "Forecasting needs a date column and a numeric metric."}

    ts = (
        df.dropna(subset=[date_col])
        .groupby(df[date_col].dt.to_period("M"))[metric]
        .sum()
        .sort_index()
    )
    if len(ts) < MIN_POINTS:
        return {"available": False, "reason": f"Need at least {MIN_POINTS} months of data; found {len(ts)}."}

    history = [{"period": str(p), "value": round(float(v), 2)} for p, v in ts.items()]
    y = ts.to_numpy(dtype=float)
    X = _seasonal_features(ts.index)

    model = LinearRegression()
    model.fit(X, y)
    fitted = model.predict(X)
    residuals = y - fitted
    resid_std = float(np.std(residuals))

    mape = float(np.mean(np.abs(residuals / np.where(y == 0, np.nan, y))) * 100)

    future_index = pd.period_range(ts.index[-1] + 1, periods=periods, freq="M")
    t_future = np.arange(len(ts), len(ts) + periods, dtype=float)
    months_future = np.array([p.month for p in future_index], dtype=float)
    X_future = np.column_stack([
        t_future,
        np.sin(2 * np.pi * months_future / 12.0),
        np.cos(2 * np.pi * months_future / 12.0),
    ])
    preds = model.predict(X_future)

    forecast = []
    for p, yhat in zip(future_index, preds):
        forecast.append({
            "period": str(p),
            "value": round(float(max(yhat, 0.0)), 2),
            "lower": round(float(max(yhat - 1.96 * resid_std, 0.0)), 2),
            "upper": round(float(yhat + 1.96 * resid_std), 2),
        })

    return {
        "available": True,
        "metric": metric,
        "date_column": date_col,
        "model": "LinearRegression(trend + monthly seasonality)",
        "mape_pct": None if np.isnan(mape) else round(mape, 2),
        "history": history,
        "forecast": forecast,
    }
