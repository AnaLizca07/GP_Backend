import pytest

@pytest.mark.asyncio
async def test_app_is_up(client):
    r = await client.get("/docs")
    assert r.status_code == 200