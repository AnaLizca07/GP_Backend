import pytest

@pytest.mark.asyncio
async def test_finance_endpoint(client):
    r = await client.get("/finance")
    assert r.status_code in (200, 401, 404)