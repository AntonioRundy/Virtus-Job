"""
Basic smoke tests for the auth API.
These tests use the real FastAPI app with a SQLite in-memory database
so no external services are required.
"""
import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionLocal = async_sessionmaker(
    test_engine, class_=AsyncSession, expire_on_commit=False
)


async def override_get_db():
    async with TestSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@pytest.fixture(autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    app.dependency_overrides[get_db] = override_get_db
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    app.dependency_overrides.clear()


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_health(client: AsyncClient):
    r = await client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "healthy"


async def test_register_success(client: AsyncClient):
    payload = {"full_name": "Teste Virtus", "email": "test@virtusjob.ao", "password": "senha1234"}
    r = await client.post("/api/v1/auth/register", json=payload)
    assert r.status_code == 201
    data = r.json()
    assert data["email"] == payload["email"]
    assert "hashed_password" not in data


async def test_register_duplicate_email(client: AsyncClient):
    payload = {"full_name": "Teste", "email": "dup@test.ao", "password": "senha1234"}
    await client.post("/api/v1/auth/register", json=payload)
    r = await client.post("/api/v1/auth/register", json=payload)
    assert r.status_code == 409


async def test_login_success(client: AsyncClient):
    reg = {"full_name": "Login User", "email": "login@test.ao", "password": "senha1234"}
    await client.post("/api/v1/auth/register", json=reg)

    r = await client.post("/api/v1/auth/login", json={"email": reg["email"], "password": reg["password"]})
    assert r.status_code == 200
    data = r.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


async def test_login_wrong_password(client: AsyncClient):
    reg = {"full_name": "Bad Auth", "email": "badauth@test.ao", "password": "senha1234"}
    await client.post("/api/v1/auth/register", json=reg)

    r = await client.post("/api/v1/auth/login", json={"email": reg["email"], "password": "wrong"})
    assert r.status_code == 401


async def test_me_authenticated(client: AsyncClient):
    reg = {"full_name": "Me User", "email": "me@test.ao", "password": "senha1234"}
    await client.post("/api/v1/auth/register", json=reg)
    login = await client.post("/api/v1/auth/login", json={"email": reg["email"], "password": reg["password"]})
    token = login.json()["access_token"]

    r = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    assert r.json()["email"] == reg["email"]


async def test_me_unauthenticated(client: AsyncClient):
    r = await client.get("/api/v1/auth/me")
    assert r.status_code == 401
