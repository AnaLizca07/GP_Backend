def test_middleware_auth_import():
    from app.middleware import auth
    assert auth is not None