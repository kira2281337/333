import uuid
from datetime import datetime, timedelta, timezone

from tests.conftest import register_and_login, set_role


async def create(client, headers, url="https://example.com/a", **extra):
    return await client.post("/links", json={"original_url": url, **extra}, headers=headers)


async def test_create_link(client):
    headers = await register_and_login(client)
    resp = await create(client, headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["original_url"] == "https://example.com/a"
    assert uuid.UUID(body["code"]).version == 4
    assert body["clicks"] == 0
    assert body["max_clicks"] is None and body["expires_at"] is None


async def test_create_link_with_expiry_and_max_clicks(client):
    headers = await register_and_login(client)
    expires = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    resp = await create(client, headers, expires_at=expires, max_clicks=10)
    assert resp.status_code == 201
    assert resp.json()["max_clicks"] == 10
    assert resp.json()["expires_at"] is not None


async def test_create_rejects_invalid_url(client):
    headers = await register_and_login(client)
    assert (await create(client, headers, url="not a url")).status_code == 422


async def test_create_rejects_past_expiry_and_bad_max_clicks(client):
    headers = await register_and_login(client)
    past = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
    assert (await create(client, headers, expires_at=past)).status_code == 422
    assert (await create(client, headers, max_clicks=0)).status_code == 422


async def test_same_url_returns_existing_code(client):
    headers = await register_and_login(client)
    first = await create(client, headers)
    second = await create(client, headers)
    assert first.status_code == 201
    assert second.status_code == 200
    assert second.json()["code"] == first.json()["code"]
    assert second.json()["id"] == first.json()["id"]
    assert len((await client.get("/links", headers=headers)).json()) == 1


async def test_same_url_different_users_gets_different_codes(client):
    h1 = await register_and_login(client, "u1@example.com")
    h2 = await register_and_login(client, "u2@example.com")
    c1 = (await create(client, h1)).json()["code"]
    c2 = (await create(client, h2)).json()["code"]
    assert c1 != c2


async def test_regular_user_limit_is_3(client):
    headers = await register_and_login(client)
    for i in range(3):
        assert (await create(client, headers, url=f"https://example.com/{i}")).status_code == 201
    resp = await create(client, headers, url="https://example.com/overflow")
    assert resp.status_code == 403


async def test_premium_user_limit_is_5(client, session_factory):
    headers = await register_and_login(client, "vip@example.com")
    await set_role(session_factory, "vip@example.com", "premium")
    for i in range(5):
        assert (await create(client, headers, url=f"https://example.com/{i}")).status_code == 201
    assert (await create(client, headers, url="https://example.com/overflow")).status_code == 403


async def test_existing_url_allowed_even_when_at_limit(client):
    headers = await register_and_login(client)
    for i in range(3):
        await create(client, headers, url=f"https://example.com/{i}")
    resp = await create(client, headers, url="https://example.com/0")
    assert resp.status_code == 200  # вернули существующую, а не отказ по лимиту


async def test_deleted_link_frees_a_slot(client):
    headers = await register_and_login(client)
    ids = []
    for i in range(3):
        ids.append((await create(client, headers, url=f"https://example.com/{i}")).json()["id"])
    assert (await create(client, headers, url="https://example.com/x")).status_code == 403
    assert (await client.delete(f"/links/{ids[0]}", headers=headers)).status_code == 204
    assert (await create(client, headers, url="https://example.com/x")).status_code == 201


async def test_expired_link_does_not_count_towards_limit(client, session_factory):
    from tests.conftest import patch_link

    headers = await register_and_login(client)
    ids = [
        (await create(client, headers, url=f"https://example.com/{i}")).json()["id"] for i in range(3)
    ]
    await patch_link(session_factory, ids[0], expires_at=datetime.now(timezone.utc) - timedelta(hours=1))
    assert (await create(client, headers, url="https://example.com/x")).status_code == 201


async def test_url_of_deleted_link_can_be_created_again_with_new_code(client):
    headers = await register_and_login(client)
    first = (await create(client, headers)).json()
    await client.delete(f"/links/{first['id']}", headers=headers)
    second = await create(client, headers)
    assert second.status_code == 201
    assert second.json()["code"] != first["code"]


async def test_list_returns_only_own_links(client):
    h1 = await register_and_login(client, "u1@example.com")
    h2 = await register_and_login(client, "u2@example.com")
    await create(client, h1, url="https://example.com/1")
    await create(client, h2, url="https://example.com/2")
    urls = [item["original_url"] for item in (await client.get("/links", headers=h1)).json()]
    assert urls == ["https://example.com/1"]


async def test_list_hides_soft_deleted(client):
    headers = await register_and_login(client)
    link = (await create(client, headers)).json()
    await client.delete(f"/links/{link['id']}", headers=headers)
    assert (await client.get("/links", headers=headers)).json() == []


async def test_delete_own_link_is_soft_delete(client, session_factory):
    from sqlalchemy import select

    from app.models import Link

    headers = await register_and_login(client)
    link = (await create(client, headers)).json()
    assert (await client.delete(f"/links/{link['id']}", headers=headers)).status_code == 204
    async with session_factory() as session:
        row = await session.scalar(select(Link).where(Link.id == link["id"]))
    assert row is not None  # строка осталась в БД
    assert row.deleted_at is not None


async def test_cannot_delete_foreign_link(client):
    h1 = await register_and_login(client, "u1@example.com")
    h2 = await register_and_login(client, "u2@example.com")
    link = (await create(client, h1)).json()
    assert (await client.delete(f"/links/{link['id']}", headers=h2)).status_code == 404
    assert len((await client.get("/links", headers=h1)).json()) == 1


async def test_delete_nonexistent_or_already_deleted_is_404(client):
    headers = await register_and_login(client)
    assert (await client.delete("/links/999", headers=headers)).status_code == 404
    link = (await create(client, headers)).json()
    await client.delete(f"/links/{link['id']}", headers=headers)
    assert (await client.delete(f"/links/{link['id']}", headers=headers)).status_code == 404
