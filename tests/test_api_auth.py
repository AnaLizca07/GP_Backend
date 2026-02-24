import pytest

@pytest.mark.asyncio
async def test_auth_endpoint(client):
    r = await client.get("/auth")
    assert r.status_code in (200, 401, 405)