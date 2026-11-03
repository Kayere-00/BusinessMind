"""Dataset upload validation and RBAC tests."""
import io

from conftest import auth_headers, register_org, upload_sample


def test_upload_csv_success(client, sample_csv):
    tokens = register_org(client)
    ds = upload_sample(client, tokens, sample_csv)
    assert ds["row_count"] > 0
    assert ds["profile"]["rows"] == ds["row_count"]
    # Stored filename must never leak the original user-supplied name.
    assert "sample" not in str(ds["profile"].get("columns"))


def test_reject_disallowed_extension(client):
    tokens = register_org(client)
    resp = client.post(
        "/api/datasets",
        files={"file": ("malware.exe", io.BytesIO(b"MZ\x90\x00evil"), "application/octet-stream")},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 415


def test_reject_php_disguised_as_csv(client):
    tokens = register_org(client)
    resp = client.post(
        "/api/datasets",
        files={"file": ("shell.php", io.BytesIO(b"<?php system($_GET['c']); ?>"), "text/csv")},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 415


def test_reject_corrupt_csv(client):
    tokens = register_org(client)
    resp = client.post(
        "/api/datasets",
        files={"file": ("broken.csv", io.BytesIO(b""), "text/csv")},
        headers=auth_headers(tokens),
    )
    assert resp.status_code == 422


def test_path_traversal_filename_sanitized(client, sample_csv):
    tokens = register_org(client)
    with open(sample_csv, "rb") as f:
        resp = client.post(
            "/api/datasets",
            files={"file": ("../../../../etc/passwd.csv", f, "text/csv")},
            headers=auth_headers(tokens),
        )
    assert resp.status_code == 201
    ds = resp.json()
    assert ".." not in ds["original_filename"]
    assert "/" not in ds["original_filename"]


def test_viewer_cannot_upload(client, sample_csv):
    admin = register_org(client)
    # Admin invites a viewer.
    created = client.post("/api/users", json={
        "full_name": "Vera Viewer", "email": "vera@viewer.com",
        "password": "Str0ngPassword!", "role": "viewer",
    }, headers=auth_headers(admin))
    assert created.status_code == 201
    viewer_login = client.post("/api/auth/login",
                               json={"email": "vera@viewer.com", "password": "Str0ngPassword!"})
    viewer = viewer_login.json()

    with open(sample_csv, "rb") as f:
        resp = client.post("/api/datasets",
                           files={"file": ("s.csv", f, "text/csv")},
                           headers=auth_headers(viewer))
    assert resp.status_code == 403


def test_only_admin_deletes_dataset(client, sample_csv):
    admin = register_org(client)
    client.post("/api/users", json={
        "full_name": "Andy Analyst", "email": "andy@analyst.com",
        "password": "Str0ngPassword!", "role": "analyst",
    }, headers=auth_headers(admin))
    analyst = client.post("/api/auth/login",
                          json={"email": "andy@analyst.com", "password": "Str0ngPassword!"}).json()
    ds = upload_sample(client, admin, sample_csv)
    assert client.delete(f"/api/datasets/{ds['id']}", headers=auth_headers(analyst)).status_code == 403
    assert client.delete(f"/api/datasets/{ds['id']}", headers=auth_headers(admin)).status_code == 204
