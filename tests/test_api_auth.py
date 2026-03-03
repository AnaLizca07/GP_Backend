import pytest

@pytest.mark.asyncio
async def test_auth_login_endpoint_exists(client):
    r = await client.post("/api/auth/login", json={"email": "x@test.com", "password": "bad"})
    # Puede responder 200 si tu API no valida, o 401/400/422 si valida
    assert r.status_code in (200, 400, 401, 422)

@pytest.mark.asyncio
async def test_auth_register_endpoint_exists(client):
    r = await client.post("/api/auth/register", json={"email": "x@test.com", "password": "123456"})
    assert r.status_code in (200, 400, 401, 422)

@pytest.mark.asyncio
async def test_auth_logout_endpoint_exists(client):
    r = await client.post("/api/auth/logout")
    assert r.status_code in (200, 400, 401, 403, 405)