import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app
from app.models import Link, User


@pytest_asyncio.fixture
async def session_factory():
    """Чистая in-memory SQLite на каждый тест (быстро, не нужен запущенный Postgres)."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield async_sessionmaker(engine, expire_on_commit=False)
    await engine.dispose()


@pytest_asyncio.fixture
async def client(session_factory):
    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    # follow_redirects=False, чтобы видеть сам 302, а не конечную страницу
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


PASSWORD = "correct-horse-battery"


async def register_and_login(client: AsyncClient, email: str = "user@example.com") -> dict[str, str]:
    """Регистрирует пользователя и возвращает заголовки с Bearer-токеном."""
    resp = await client.post("/auth/register", json={"email": email, "password": PASSWORD})
    assert resp.status_code == 201, resp.text
    resp = await client.post("/auth/token", data={"username": email, "password": PASSWORD})
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def set_role(session_factory, email: str, role: str) -> None:
    async with session_factory() as session:
        await session.execute(update(User).where(User.email == email).values(role=role))
        await session.commit()


async def patch_link(session_factory, link_id: int, **values) -> None:
    """Прямое изменение строки в БД (например, чтобы сделать ссылку истёкшей)."""
    async with session_factory() as session:
        await session.execute(update(Link).where(Link.id == link_id).values(**values))
        await session.commit()
