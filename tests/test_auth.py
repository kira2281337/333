from sqlalchemy import select

from app.models import User
from tests.conftest import PASSWORD, register_and_login


async def test_register_creates_user_with_default_role(client):
    resp = await client.post("/auth/register", json={"email": "a@example.com", "password": PASSWORD})
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == "a@example.com"
    assert body["role"] == "user"
    assert "password" not in body and "hashed_password" not in body


async def test_password_is_stored_as_argon2id_hash(client, session_factory):
    await client.post("/auth/register", json={"email": "a@example.com", "password": PASSWORD})
    async with session_factory() as session:
        user = await session.scalar(select(User))
    assert user.hashed_password.startswith("$argon2id$")


async def test_register_duplicate_email_conflict(client):
    await client.post("/auth/register", json={"email": "a@example.com", "password": PASSWORD})
    resp = await client.post("/auth/register", json={"email": "A@example.com", "password": PASSWORD})
    assert resp.status_code == 409


async def test_register_short_password_rejected(client):
    resp = await client.post("/auth/register", json={"email": "a@example.com", "password": "short"})
    assert resp.status_code == 422


async def test_login_success_returns_bearer_token(client):
    await client.post("/auth/register", json={"email": "a@example.com", "password": PASSWORD})
    resp = await client.post("/auth/token", data={"username": "a@example.com", "password": PASSWORD})
    assert resp.status_code == 200
    assert resp.json()["token_type"] == "bearer"
    assert resp.json()["access_token"]


async def test_login_wrong_password(client):
    await client.post("/auth/register", json={"email": "a@example.com", "password": PASSWORD})
    resp = await client.post("/auth/token", data={"username": "a@example.com", "password": "wrong-password"})
    assert resp.status_code == 401


async def test_login_unknown_user(client):
    resp = await client.post("/auth/token", data={"username": "nobody@example.com", "password": PASSWORD})
    assert resp.status_code == 401


async def test_me_requires_token(client):
    assert (await client.get("/auth/me")).status_code == 401


async def test_me_with_token(client):
    headers = await register_and_login(client, "a@example.com")
    resp = await client.get("/auth/me", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == "a@example.com"


async def test_invalid_token_rejected(client):
    resp = await client.get("/auth/me", headers={"Authorization": "Bearer garbage"})
    assert resp.status_code == 401


async def test_links_endpoints_require_auth(client):
    assert (await client.get("/links")).status_code == 401
    assert (await client.post("/links", json={"original_url": "https://example.com"})).status_code == 401
    assert (await client.delete("/links/1")).status_code == 401
