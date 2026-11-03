"""Deterministic business analytics: KPIs, trends, anomalies, correlations, insights.

Every number returned here is computed from the actual uploaded dataset.
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

PRIMARY_METRIC_HINTS = ["revenue", "sales", "amount", "total", "profit", "income", "value"]


def pick_primary_metric(df: pd.DataFrame) -> str | None:
    numeric = df.select_dtypes(include="number").columns.tolist()
    if not numeric:
        return None
    lowered = {c: c.lower() for c in numeric}
    for hint in PRIMARY_METRIC_HINTS:
        for col, low in lowered.items():
            if hint in low:
                return col
    return numeric[0]


def pick_date_column(df: pd.DataFrame) -> str | None:
    dates = [c for c in df.columns if pd.api.types.is_datetime64_any_dtype(df[c])]
    return dates[0] if dates else None


def _f(v: Any) -> float | None:
    if v is None or (isinstance(v, float) and (np.isnan(v) or np.isinf(v))):
        return None
    return float(v)


def compute_kpis(df: pd.DataFrame) -> dict[str, Any]:
    metric = pick_primary_metric(df)
    date_col = pick_date_column(df)
    kpis: dict[str, Any] = {
        "row_count": int(len(df)),
        "column_count": int(len(df.columns)),
        "primary_metric": metric,
        "date_column": date_col,
    }
    if metric:
        kpis["metric_total"] = _f(df[metric].sum())
        kpis["metric_mean"] = _f(df[metric].mean())
        kpis["metric_max"] = _f(df[metric].max())
        kpis["metric_min"] = _f(df[metric].min())
    if date_col:
        kpis["date_min"] = str(df[date_col].min().date())
        kpis["date_max"] = str(df[date_col].max().date())
        if metric:
            ts = df.dropna(subset=[date_col]).groupby(df[date_col].dt.to_period("M"))[metric].sum()
            if len(ts) >= 2:
                first, last = float(ts.iloc[0]), float(ts.iloc[-1])
                kpis["growth_first_last_pct"] = (
                    round((last - first) / abs(first) * 100, 2) if first != 0 else None
                )
                kpis["best_month"] = str(ts.idxmax())
                kpis["worst_month"] = str(ts.idxmin())
    return kpis


def compute_timeseries(df: pd.DataFrame, metric: str | None = None, freq: str = "M") -> dict[str, Any]:
    date_col = pick_date_column(df)
    metric = metric or pick_primary_metric(df)
    if not date_col or not metric:
        return {"available": False, "reason": "Dataset needs a date column and a numeric metric."}
    freq = freq if freq in {"D", "W", "M", "Q"} else "M"
    ts = (
        df.dropna(subset=[date_col])
        .groupby(df[date_col].dt.to_period(freq))[metric]
        .sum()
        .sort_index()
    )
    return {
        "available": True,
        "metric": metric,
        "date_column": date_col,
        "freq": freq,
        "points": [{"period": str(p), "value": _f(v)} for p, v in ts.items()],
    }


def compute_breakdown(df: pd.DataFrame, by: str | None = None, metric: str | None = None, top: int = 8) -> dict[str, Any]:
    metric = metric or pick_primary_metric(df)
    cats = df.select_dtypes(include=["object", "category", "bool"]).columns.tolist()
    if by is None:
        # Pick the categorical column with a reasonable cardinality.
        candidates = [c for c in cats if 1 < df[c].nunique() <= 50]
        by = candidates[0] if candidates else None
    if not by or not metric or by not in df.columns or metric not in df.columns:
        return {"available": False, "reason": "Need a categorical column and a numeric metric."}
    grouped = df.groupby(by, dropna=False)[metric].sum().sort_values(ascending=False).head(top)
    total = float(df[metric].sum())
    return {
        "available": True,
        "metric": metric,
        "by": by,
        "items": [
            {"label": str(k), "value": _f(v), "share_pct": round(float(v) / total * 100, 2) if total else None}
            for k, v in grouped.items()
        ],
    }


def compute_anomalies(df: pd.DataFrame, metric: str | None = None, z: float = 2.5) -> dict[str, Any]:
    metric = metric or pick_primary_metric(df)
    if not metric or metric not in df.columns:
        return {"available": False, "reason": "No numeric metric available."}
    series = df[metric].astype(float)
    std = float(series.std())
    if std == 0 or np.isnan(std):
        return {"available": True, "metric": metric, "anomalies": [], "threshold_z": z}
    zscores = (series - series.mean()) / std
    mask = zscores.abs() > z
    cols = [c for c in df.columns[:6]]
    rows = []
    for idx in df.index[mask][:20]:
        row = {c: _cell(df.at[idx, c]) for c in cols}
        row["z_score"] = round(float(zscores.loc[idx]), 2)
        rows.append(row)
    return {
        "available": True,
        "metric": metric,
        "threshold_z": z,
        "count": int(mask.sum()),
        "anomalies": rows,
    }


def compute_correlations(df: pd.DataFrame) -> dict[str, Any]:
    numeric = df.select_dtypes(include="number")
    if numeric.shape[1] < 2:
        return {"available": False, "reason": "Need at least two numeric columns."}
    corr = numeric.corr(numeric_only=True).round(3)
    pairs = []
    cols = corr.columns.tolist()
    for i in range(len(cols)):
        for j in range(i + 1, len(cols)):
            v = corr.iloc[i, j]
            if not np.isnan(v):
                pairs.append({"a": cols[i], "b": cols[j], "r": float(v)})
    pairs.sort(key=lambda p: abs(p["r"]), reverse=True)
    return {"available": True, "strongest": pairs[:8]}


def _cell(v: Any) -> Any:
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating,)):
        return None if np.isnan(v) else float(v)
    if isinstance(v, (pd.Timestamp,)):
        return str(v.date())
    if v is pd.NaT or (isinstance(v, float) and np.isnan(v)):
        return None
    return v


def compute_insights(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Auto-generated, fully data-grounded insight statements."""
    insights: list[dict[str, Any]] = []
    metric = pick_primary_metric(df)
    date_col = pick_date_column(df)

    kpis = compute_kpis(df)
    if metric:
        insights.append({
            "kind": "kpi",
            "title": f"Total {metric}",
            "body": f"The dataset contains {len(df):,} rows. Total {metric} is "
                    f"{kpis.get('metric_total'):,.2f}, averaging {kpis.get('metric_mean'):,.2f} per row.",
        })
    if date_col and metric and "growth_first_last_pct" in kpis:
        g = kpis["growth_first_last_pct"]
        direction = "grew" if (g or 0) >= 0 else "declined"
        insights.append({
            "kind": "trend",
            "title": f"{metric} trend",
            "body": f"Monthly {metric} {direction} by {abs(g or 0):.1f}% from the first month "
                    f"({kpis['date_min']}) to the last ({kpis['date_max']}). "
                    f"Best month: {kpis.get('best_month')}; weakest: {kpis.get('worst_month')}.",
        })

    breakdown = compute_breakdown(df)
    if breakdown.get("available") and breakdown["items"]:
        top = breakdown["items"][0]
        insights.append({
            "kind": "concentration",
            "title": f"Top {breakdown['by']}",
            "body": f"'{top['label']}' leads {breakdown['by']} with {top['value']:,.2f} "
                    f"({top['share_pct']:.1f}% of total {breakdown['metric']}).",
        })

    anomalies = compute_anomalies(df)
    if anomalies.get("available"):
        insights.append({
            "kind": "anomaly",
            "title": f"Outliers in {anomalies.get('metric')}",
            "body": f"{anomalies.get('count', 0)} rows exceed |z| > {anomalies.get('threshold_z')} "
                    f"on {anomalies.get('metric')} — worth reviewing for errors or exceptional events.",
        })

    corr = compute_correlations(df)
    if corr.get("available") and corr["strongest"]:
        s = corr["strongest"][0]
        insights.append({
            "kind": "correlation",
            "title": "Strongest relationship",
            "body": f"'{s['a']}' and '{s['b']}' have the strongest correlation (r = {s['r']:.2f}).",
        })
    return insights
