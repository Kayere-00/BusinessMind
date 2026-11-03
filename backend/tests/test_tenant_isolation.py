"""Multi-tenant isolation tests — the core security guarantee."""
from conftest import auth_headers, register_org, upload_sample


def test_dataset_isolation_between_orgs(client, sample_csv):
    org_a = register_org(client)
    org_b = register_org(client)
    ds = upload_sample(client, org_a, sample_csv)

    # Org B cannot read, analyze, or delete Org A's dataset — always 404.
    assert client.get(f"/api/datasets/{ds['id']}", headers=auth_headers(org_b)).status_code == 404
    assert client.get(f"/api/datasets/{ds['id']}/preview", headers=auth_headers(org_b)).status_code == 404
    assert client.get(f"/api/analytics/{ds['id']}/kpis", headers=auth_headers(org_b)).status_code == 404
    assert client.get(f"/api/analytics/{ds['id']}/forecast", headers=auth_headers(org_b)).status_code == 404
    assert client.delete(f"/api/datasets/{ds['id']}", headers=auth_headers(org_b)).status_code == 404
    # Assistant is scoped too.
    resp = client.post("/api/assistant/ask",
                       json={"dataset_id": ds["id"], "question": "total revenue"},
                       headers=auth_headers(org_b))
    assert resp.status_code == 404

    # Each org sees only its own datasets.
    listed_b = client.get("/api/datasets", headers=auth_headers(org_b)).json()
    assert all(d["id"] != ds["id"] for d in listed_b)
    listed_a = client.get("/api/datasets", headers=auth_headers(org_a)).json()
    assert any(d["id"] == ds["id"] for d in listed_a)


def test_user_list_scoped_to_org(client):
    org_a = register_org(client)
    org_b = register_org(client)
    users_a = client.get("/api/users", headers=auth_headers(org_a)).json()
    users_b = client.get("/api/users", headers=auth_headers(org_b)).json()
    emails_a = {u["email"] for u in users_a}
    emails_b = {u["email"] for u in users_b}
    assert emails_a.isdisjoint(emails_b)


def test_report_isolation(client, sample_csv):
    org_a = register_org(client)
    org_b = register_org(client)
    ds = upload_sample(client, org_a, sample_csv)
    rep = client.post("/api/reports",
                      json={"dataset_id": ds["id"], "title": "Quarterly Review"},
                      headers=auth_headers(org_a))
    assert rep.status_code == 201, rep.text
    rep_id = rep.json()["id"]
    assert client.get(f"/api/reports/{rep_id}/download", headers=auth_headers(org_b)).status_code == 404
    assert client.delete(f"/api/reports/{rep_id}", headers=auth_headers(org_b)).status_code == 404
