"""Authentication flow tests."""


def test_register_and_login(client):
    resp = client.post("/api/auth/register", json={
        "org_name": "Acme Corp", "full_name": "Alice Admin",
        "email": "alice@acme.com", "password": "Str0ngPassword!",
    })
    assert resp.status_code == 201
    tokens = resp.json()
    assert tokens["token_type"] == "bearer"

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"})
    assert me.status_code == 200
    assert me.json()["email"] == "alice@acme.com"
    assert me.json()["role"] == "admin"
    assert me.json()["org_name"] == "Acme Corp"

    login = client.post("/api/auth/login", json={"email": "alice@acme.com", "password": "Str0ngPassword!"})
    assert login.status_code == 200


def test_weak_password_rejected(client):
    resp = client.post("/api/auth/register", json={
        "org_name": "WeakOrg", "full_name": "Bob Weak",
        "email": "bob@weak.com", "password": "short",
    })
    assert resp.status_code == 422


def test_duplicate_email_rejected(client):
    body = {"org_name": "OrgA", "full_name": "A", "email": "dup@x.com", "password": "Str0ngPassword!"}
    body["full_name"] = "User One"
    assert client.post("/api/auth/register", json=body).status_code == 201
    body2 = {"org_name": "OrgB", "full_name": "User Two", "email": "dup@x.com", "password": "Str0ngPassword!"}
    assert client.post("/api/auth/register", json=body2).status_code == 409


def test_cannot_self_join_existing_org(client):
    client.post("/api/auth/register", json={
        "org_name": "TakenOrg", "full_name": "First", "email": "first@taken.com", "password": "Str0ngPassword!",
    })
    resp = client.post("/api/auth/register", json={
        "org_name": "TakenOrg", "full_name": "Second", "email": "second@taken.com", "password": "Str0ngPassword!",
    })
    assert resp.status_code == 409


def test_wrong_password_generic_error(client):
    client.post("/api/auth/register", json={
        "org_name": "PwOrg", "full_name": "C", "email": "c@pw.com", "password": "Str0ngPassword!",
    })
    resp = client.post("/api/auth/login", json={"email": "c@pw.com", "password": "Wr0ngPassword!"})
    assert resp.status_code == 401
    assert "Invalid email or password" in resp.json()["detail"]


def test_refresh_rotation_and_logout(client):
    from conftest import register_org
    tokens = register_org(client)
    r1 = client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r1.status_code == 200
    # Old refresh token is single-use (rotation):
    r2 = client.post("/api/auth/refresh", json={"refresh_token": tokens["refresh_token"]})
    assert r2.status_code == 401
    # Logout revokes the new one:
    new_refresh = r1.json()["refresh_token"]
    assert client.post("/api/auth/logout", json={"refresh_token": new_refresh}).status_code == 204
    assert client.post("/api/auth/refresh", json={"refresh_token": new_refresh}).status_code == 401


def test_protected_route_requires_token(client):
    assert client.get("/api/datasets").status_code in (401, 403)


def test_tampered_token_rejected(client):
    from conftest import register_org
    tokens = register_org(client)
    bad = tokens["access_token"][:-3] + "abc"
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {bad}"}).status_code == 401
