import pytest

@pytest.mark.asyncio
async def test_employees_list(client):
    r = await client.get("/employees")
    assert r.status_code in (200, 404)  