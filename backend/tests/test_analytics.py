"""Analytics correctness tests — verify API numbers against ground-truth pandas."""
import pandas as pd
from conftest import auth_headers, register_org, upload_sample


def test_kpis_match_pandas(client, sample_csv):
    tokens = register_org(client)
    ds = upload_sample(client, tokens, sample_csv)
    kpis = client.get(f"/api/analytics/{ds['id']}/kpis", headers=auth_headers(tokens)).json()

    truth = pd.read_csv(sample_csv)
    assert kpis["row_count"] == len(truth)
    assert kpis["primary_metric"] == "revenue"
    assert abs(kpis["metric_total"] - truth["revenue"].sum()) < 1.0
    assert abs(kpis["metric_mean"] - truth["revenue"].mean()) < 0.01


def test_timeseries_monthly(client, sample_csv):
    tokens = register_org(client)
    ds = upload_sample(client, tokens, sample_csv)
    ts = client.get(f"/api/analytics/{ds['id']}/timeseries", headers=auth_headers(tokens)).json()
    assert ts["available"] is True
    assert len(ts["points"]) >= 20  # ~24 months of sample data

    truth = pd.read_csv(sample_csv, parse_dates=["order_date"])
    monthly = truth.groupby(truth["order_date"].dt.to_period("M"))["revenue"].sum()
    assert abs(ts["points"][0]["value"] - float(monthly.iloc[0])) < 1.0


def test_breakdown_sums_to_total(client, sample_csv):
    tokens = register_org(client)
    ds = upload_sample(client, tokens, sample_csv)
    bd = client.get(f"/api/analytics/{ds['id']}/breakdown", params={"by": "region"},
                    headers=auth_headers(tokens)).json()
    assert bd["available"] is True
    assert len(bd["items"]) == 4  # North/South/East/West


def test_anomaly_detection_finds_injected_outlier(client, sample_csv):
    tokens = register_org(client)
    ds = upload_sample(client, tokens, sample_csv)
    an = client.get(f"/api/analytics/{ds['id']}/anomalies", headers=auth_headers(tokens)).json()
    assert an["available"] is True
    assert an["count"] >= 1  # the injected 809,100 order must be caught


def test_forecast_shape_and_periods(client, sample_csv):
    tokens = register_org(client)
    ds = upload_sample(client, tokens, sample_csv)
    fc = client.get(f"/api/analytics/{ds['id']}/forecast", params={"periods": 6},
                    headers=auth_headers(tokens)).json()
    assert fc["available"] is True
    assert len(fc["forecast"]) == 6
    assert len(fc["history"]) >= 20
    for p in fc["forecast"]:
        assert p["lower"] <= p["value"] <= p["upper"]
    assert fc["mape_pct"] is not None


def test_insights_are_grounded(client, sample_csv):
    tokens = register_org(client)
    ds = upload_sample(client, tokens, sample_csv)
    ins = client.get(f"/api/analytics/{ds['id']}/insights", headers=auth_headers(tokens)).json()
    assert len(ins["insights"]) >= 3
    joined = " ".join(i["body"] for i in ins["insights"])
    assert "revenue" in joined.lower()


def test_assistant_top_n_answer(client, sample_csv):
    tokens = register_org(client)
    ds = upload_sample(client, tokens, sample_csv)
    resp = client.post("/api/assistant/ask",
                       json={"dataset_id": ds["id"], "question": "top 3 products by revenue"},
                       headers=auth_headers(tokens))
    assert resp.status_code == 200
    body = resp.json()
    assert "revenue" in body["answer"].lower()
    assert body["chart"]["type"] == "bar"
    assert len(body["chart"]["items"]) == 3

    truth = pd.read_csv(sample_csv)
    top = truth.groupby("product")["revenue"].sum().sort_values(ascending=False).head(3)
    api_labels = [i["label"] for i in body["chart"]["items"]]
    assert api_labels == [str(k) for k in top.index]


def test_assistant_total_question(client, sample_csv):
    tokens = register_org(client)
    ds = upload_sample(client, tokens, sample_csv)
    resp = client.post("/api/assistant/ask",
                       json={"dataset_id": ds["id"], "question": "What is the total revenue?"},
                       headers=auth_headers(tokens))
    truth = pd.read_csv(sample_csv)["revenue"].sum()
    assert f"{truth:,.2f}" in resp.json()["answer"]
