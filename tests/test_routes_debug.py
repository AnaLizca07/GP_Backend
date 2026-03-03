def test_list_routes():
    from app.main import app
    paths = sorted([r.path for r in app.router.routes])
    print("\n".join(paths))
    assert len(paths) > 0