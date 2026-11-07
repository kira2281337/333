import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.models import Link
from tests.conftest import patch_link, register_and_login


async def make_link(client, headers, **extra):
    resp = await client.post(
        "/links", json={"original_url": "https://example.com/target", **extra}, headers=headers
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


async def get_clicks(session_factory, link_id: int) -> int:
    async with session_factory() as session:
        return await session.scalar(select(Link.clicks).where(Link.id == link_id))


async def test_redirect_302_and_click_counter(client, session_factory):
    headers = await register_and_login(client)
    link = await make_link(client, headers)

    resp = await client.get(f"/{link['code']}")  # публичный эндпоинт: без токена
    assert resp.status_code == 302
    assert resp.headers["location"] == "https://example.com/target"
    assert await get_clicks(session_factory, link["id"]) == 1

    await client.get(f"/{link['code']}")
    assert await get_clicks(session_factory, link["id"]) == 2


async def test_unknown_code_is_404(client):
    assert (await client.get(f"/{uuid.uuid4()}")).status_code == 404


async def test_malformed_code_is_404(client):
    assert (await client.get("/not-a-uuid")).status_code == 404


async def test_soft_deleted_is_404(client):
    headers = await register_and_login(client)
    link = await make_link(client, headers)
    await client.delete(f"/links/{link['id']}", headers=headers)
    assert (await client.get(f"/{link['code']}")).status_code == 404


async def test_expired_by_date_is_419_and_not_counted(client, session_factory):
    headers = await register_and_login(client)
    link = await make_link(client, headers)
    await patch_link(session_factory, link["id"], expires_at=datetime.now(timezone.utc) - timedelta(seconds=1))
    assert (await client.get(f"/{link['code']}")).status_code == 419
    assert await get_clicks(session_factory, link["id"]) == 0


async def test_not_yet_expired_still_redirects(client):
    headers = await register_and_login(client)
    expires = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    link = await make_link(client, headers, expires_at=expires)
    assert (await client.get(f"/{link['code']}")).status_code == 302


async def test_max_clicks_exhausted_is_419(client, session_factory):
    headers = await register_and_login(client)
    link = await make_link(client, headers, max_clicks=2)
    assert (await client.get(f"/{link['code']}")).status_code == 302
    assert (await client.get(f"/{link['code']}")).status_code == 302
    assert (await client.get(f"/{link['code']}")).status_code == 419
    assert await get_clicks(session_factory, link["id"]) == 2  # счётчик не вышел за лимит


async def test_static_routes_not_shadowed_by_code_route(client):
    headers = await register_and_login(client)
    assert (await client.get("/links", headers=headers)).status_code == 200
    assert (await client.get("/docs")).status_code == 200
