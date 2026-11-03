"""Professional PDF business reports (reportlab)."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from . import analysis
from .forecasting import forecast_metric

ACCENT = colors.HexColor("#2563eb")
DARK = colors.HexColor("#0f172a")
MUTED = colors.HexColor("#64748b")


def generate_report(df: pd.DataFrame, title: str, dataset_name: str, org_name: str, out_path: Path) -> dict[str, Any]:
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("h1", parent=styles["Title"], textColor=DARK, fontSize=22, spaceAfter=6)
    h2 = ParagraphStyle("h2", parent=styles["Heading2"], textColor=ACCENT, fontSize=14, spaceBefore=14)
    body = ParagraphStyle("body", parent=styles["BodyText"], textColor=DARK, fontSize=10.5, leading=15)
    muted = ParagraphStyle("muted", parent=body, textColor=MUTED, fontSize=9)

    doc = SimpleDocTemplate(
        str(out_path), pagesize=A4,
        leftMargin=2 * cm, rightMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm,
        title=title, author="BusinessMind AI",
    )
    story: list = []

    story.append(Paragraph(title, h1))
    story.append(Paragraph(
        f"{org_name} · Dataset: {dataset_name} · Generated "
        f"{datetime.now(timezone.utc):%Y-%m-%d %H:%M UTC} by BusinessMind AI", muted))
    story.append(Spacer(1, 12))

    # ---- KPIs ----
    kpis = analysis.compute_kpis(df)
    story.append(Paragraph("Key Performance Indicators", h2))
    kpi_rows = [["Metric", "Value"]]
    kpi_rows.append(["Rows analyzed", f"{kpis['row_count']:,}"])
    if kpis.get("primary_metric"):
        m = kpis["primary_metric"]
        kpi_rows += [
            [f"Total {m}", f"{kpis['metric_total']:,.2f}"],
            [f"Average {m}", f"{kpis['metric_mean']:,.2f}"],
            [f"Max / Min {m}", f"{kpis['metric_max']:,.2f} / {kpis['metric_min']:,.2f}"],
        ]
    if kpis.get("date_min"):
        kpi_rows.append(["Period covered", f"{kpis['date_min']} → {kpis['date_max']}"])
    if kpis.get("growth_first_last_pct") is not None:
        kpi_rows.append(["First→last month growth", f"{kpis['growth_first_last_pct']:+.1f}%"])
    story.append(_styled_table(kpi_rows))

    # ---- Insights ----
    story.append(Paragraph("AI Insights (computed from this dataset)", h2))
    for ins in analysis.compute_insights(df):
        story.append(Paragraph(f"• <b>{ins['title']}.</b> {ins['body']}", body))
        story.append(Spacer(1, 4))

    # ---- Breakdown ----
    breakdown = analysis.compute_breakdown(df)
    if breakdown.get("available"):
        story.append(Paragraph(f"{breakdown['metric']} by {breakdown['by']} (top {len(breakdown['items'])})", h2))
        rows = [[breakdown["by"], breakdown["metric"], "Share %"]]
        rows += [[i["label"], f"{i['value']:,.2f}", f"{i['share_pct']:.1f}%"] for i in breakdown["items"]]
        story.append(_styled_table(rows))

    # ---- Forecast ----
    fc = forecast_metric(df, periods=6)
    if fc.get("available"):
        story.append(Paragraph(f"6-month forecast — {fc['metric']}", h2))
        story.append(Paragraph(f"Model: {fc['model']} · MAPE: {fc['mape_pct']}%", muted))
        rows = [["Month", "Forecast", "Lower", "Upper"]]
        rows += [[p["period"], f"{p['value']:,.2f}", f"{p['lower']:,.2f}", f"{p['upper']:,.2f}"] for p in fc["forecast"]]
        story.append(_styled_table(rows))

    # ---- Anomalies ----
    an = analysis.compute_anomalies(df)
    if an.get("available"):
        story.append(Paragraph("Anomaly review", h2))
        story.append(Paragraph(
            f"{an['count']} rows exceed |z| > {an['threshold_z']} on '{an['metric']}'. "
            "These warrant manual review for data-entry errors or exceptional business events.", body))

    doc.build(story)
    return {"kpis": kpis}


def _styled_table(rows: list[list[str]]) -> Table:
    table = Table(rows, hAlign="LEFT")
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), ACCENT),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f1f5f9")]),
        ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("RIGHTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
    ]))
    return table
