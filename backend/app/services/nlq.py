"""Natural-language question engine — deterministic and data-grounded.

Parses a business question, maps it onto real dataset columns, runs the
corresponding pandas computation, and returns a structured result. No number
in the answer is ever invented; the optional LLM layer only *narrates* these
computed facts.
"""
from __future__ import annotations

import re
from typing import Any

import numpy as np
import pandas as pd

from . import analysis


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", s.lower()).strip()


def _match_column(question: str, columns: list[str], hints: dict[str, str] | None = None) -> str | None:
    q = _norm(question)
    best, best_len = None, 0
    for col in columns:
        for cand in {_norm(col), _norm(col).replace(" ", "")}:
            if cand and cand in q.replace(" ", " "):
                if len(cand) > best_len:
                    best, best_len = col, len(cand)
    if best is None and hints:
        for hint, col in hints.items():
            if hint in q:
                return col
    return best


def answer_question(df: pd.DataFrame, question: str) -> dict[str, Any]:
    q = question.lower()
    numeric = df.select_dtypes(include="number").columns.tolist()
    categorical = df.select_dtypes(include=["object", "category", "bool"]).columns.tolist()
    date_col = analysis.pick_date_column(df)
    primary = analysis.pick_primary_metric(df)
    metric = _match_column(q, numeric) or primary

    # ---- Intent: forecasting -------------------------------------------------
    if re.search(r"\b(forecast|predict|projection|next \d+ months?|future)\b", q):
        from .forecasting import forecast_metric
        m = re.search(r"next (\d+)", q)
        periods = int(m.group(1)) if m else 6
        fc = forecast_metric(df, metric, periods)
        if not fc.get("available"):
            return {"answer": f"I can't forecast yet: {fc.get('reason')}", "chart": None, "table": None, "computed": fc}
        total_fc = sum(p["value"] for p in fc["forecast"])
        return {
            "answer": (
                f"Forecast for {fc['metric']} over the next {periods} months totals "
                f"{total_fc:,.2f}. Model: {fc['model']} (MAPE {fc['mape_pct']}%)."
            ),
            "chart": {"type": "forecast", "history": fc["history"], "forecast": fc["forecast"], "metric": fc["metric"]},
            "table": None,
            "computed": {"forecast": fc["forecast"], "mape_pct": fc["mape_pct"], "metric": fc["metric"]},
        }

    # ---- Intent: anomalies ---------------------------------------------------
    if re.search(r"\b(anomal|outlier|unusual|spike|abnormal)\b", q):
        an = analysis.compute_anomalies(df, metric)
        if not an.get("available"):
            return {"answer": an.get("reason", "Not available."), "chart": None, "table": None, "computed": an}
        return {
            "answer": f"Found {an['count']} anomalous rows in '{an['metric']}' (|z| > {an['threshold_z']}).",
            "chart": None,
            "table": {"rows": an["anomalies"]},
            "computed": {"count": an["count"], "metric": an["metric"]},
        }

    # ---- Intent: top-N by metric --------------------------------------------
    m = re.search(r"top\s+(\d+)?\s*([a-z0-9_ ]*?)\s+by\s+([a-z0-9_ ]+)", q)
    if m:
        n = int(m.group(1)) if m.group(1) else 5
        by = _match_column(m.group(2) or "", categorical) or (categorical[0] if categorical else None)
        met = _match_column(m.group(3), numeric) or metric
        if by and met:
            grouped = df.groupby(by)[met].sum().sort_values(ascending=False).head(n)
            items = [{"label": str(k), "value": round(float(v), 2)} for k, v in grouped.items()]
            return {
                "answer": f"Top {n} {by} by {met}: " + ", ".join(f"{i['label']} ({i['value']:,.2f})" for i in items) + ".",
                "chart": {"type": "bar", "items": items, "metric": met, "by": by},
                "table": {"rows": items},
                "computed": {"items": items, "metric": met, "by": by},
            }

    # ---- Intent: trend over time ---------------------------------------------
    if re.search(r"\b(trend|over time|by month|per month|monthly|each month|evolution|growth)\b", q):
        ts = analysis.compute_timeseries(df, metric)
        if not ts.get("available"):
            return {"answer": ts.get("reason", "No time column available."), "chart": None, "table": None, "computed": ts}
        pts = ts["points"]
        first, last = pts[0]["value"], pts[-1]["value"]
        change = (last - first) / abs(first) * 100 if first else 0.0
        return {
            "answer": (
                f"Monthly {ts['metric']} went from {first:,.2f} ({pts[0]['period']}) to "
                f"{last:,.2f} ({pts[-1]['period']}) — a {change:+.1f}% change."
            ),
            "chart": {"type": "line", "points": pts, "metric": ts["metric"]},
            "table": None,
            "computed": {"points": pts, "change_pct": round(change, 2), "metric": ts["metric"]},
        }

    # ---- Intent: aggregations -------------------------------------------------
    if metric:
        if re.search(r"\b(total|sum|overall)\b", q):
            val = float(df[metric].sum())
            return {"answer": f"The total {metric} is {val:,.2f} across {len(df):,} rows.",
                    "chart": None, "table": None, "computed": {"metric": metric, "total": val}}
        if re.search(r"\b(average|avg|mean)\b", q):
            val = float(df[metric].mean())
            return {"answer": f"The average {metric} is {val:,.2f}.",
                    "chart": None, "table": None, "computed": {"metric": metric, "mean": val}}
        if re.search(r"\b(max|maximum|highest|largest|biggest)\b", q):
            idx = df[metric].idxmax()
            val = float(df.loc[idx, metric])
            context = {c: analysis._cell(df.loc[idx, c]) for c in df.columns[:5]}
            return {"answer": f"The highest {metric} is {val:,.2f}.", "chart": None,
                    "table": {"rows": [context]}, "computed": {"metric": metric, "max": val}}
        if re.search(r"\b(min|minimum|lowest|smallest)\b", q):
            val = float(df[metric].min())
            return {"answer": f"The lowest {metric} is {val:,.2f}.",
                    "chart": None, "table": None, "computed": {"metric": metric, "min": val}}

    if re.search(r"\b(how many|count|number of rows|records)\b", q):
        return {"answer": f"The dataset contains {len(df):,} rows and {len(df.columns)} columns.",
                "chart": None, "table": None, "computed": {"rows": len(df), "cols": len(df.columns)}}

    # ---- Fallback: KPI summary -------------------------------------------------
    kpis = analysis.compute_kpis(df)
    lines = [f"Rows: {kpis['row_count']:,}, columns: {kpis['column_count']}."]
    if kpis.get("primary_metric"):
        lines.append(f"Total {kpis['primary_metric']}: {kpis['metric_total']:,.2f} "
                     f"(avg {kpis['metric_mean']:,.2f}).")
    if kpis.get("date_min"):
        lines.append(f"Period: {kpis['date_min']} → {kpis['date_max']}.")
    return {"answer": "Here's a quick summary. " + " ".join(lines) +
            " Try asking things like 'top 5 products by revenue', 'monthly sales trend', "
            "'forecast next 6 months', or 'any anomalies in expenses?'.",
            "chart": None, "table": None, "computed": kpis}
