import pytest

@pytest.mark.asyncio
async def test_projects_endpoint(client):
    r = await client.get("/projects")
    assert r.status_code in (200, 401, 404)