import pytest

from app.services import auth


def test_services_auth_import():
    # prueba básica: el módulo carga
    assert auth is not None


def test_password_hash_and_verify_ok():
    password = "123456"
    hashed = auth.get_password_hash(password)

    assert hashed is not None
    assert isinstance(hashed, str)
    assert hashed != password

    ok = auth.verify_password(password, hashed)
    assert ok is True


def test_password_verify_fail():
    hashed = auth.get_password_hash("123456")
    ok = auth.verify_password("otra_clave", hashed)
    assert ok is False


def test_create_access_token_returns_string():
    # payload mínimo típico
    data = {"sub": "test@example.com"}
    token = auth.create_access_token(data)

    assert token is not None
    assert isinstance(token, str)
    assert len(token) > 10


def test_decode_access_token_ok():
    data = {"sub": "test@example.com"}
    token = auth.create_access_token(data)

    payload = auth.decode_access_token(token)

    assert payload is not None
    assert payload.get("sub") == "test@example.com"


def test_decode_access_token_invalid():
    with pytest.raises(Exception):
        auth.decode_access_token("token_invalido")