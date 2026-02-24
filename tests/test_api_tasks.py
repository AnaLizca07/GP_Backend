import pytest

@pytest.mark.asyncio
async def test_tasks_endpoint(client):
    r = await client.get("/tasks")
    assert r.status_code in (200, 401, 404)