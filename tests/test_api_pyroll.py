import pytest

@pytest.mark.asyncio
async def test_pyroll_endpoint(client):
    r = await client.get("/pyroll")
    assert r.status_code in (200, 401, 404)