import pytest
from fastapi import HTTPException

from app.services.auth import AuthService


# ---------- FAKES / MOCKS ----------
class FakeUser:
    def __init__(self, user_id="u1", email="test@mail.com"):
        self.id = user_id
        self.email = email


class FakeUserResponse:
    def __init__(self, user=None):
        self.user = user


class FakeSession:
    def __init__(self, access_token="token123", expires_in=3600):
        self.access_token = access_token
        self.expires_in = expires_in


class FakeAuthResponse:
    def __init__(self, user=None, session=None):
        self.user = user
        self.session = session


class FakeTableQuery:
    def __init__(self, data):
        self.data = data

    def select(self, *_args, **_kwargs):
        return self

    def eq(self, *_args, **_kwargs):
        return self

    def insert(self, *_args, **_kwargs):
        return self

    def execute(self):
        class R:
            pass
        r = R()
        r.data = self.data
        return r


class FakeSupabase:
    def __init__(self):
        self.auth = self.FakeAuth()
        self._tables = {}

    class FakeAuth:
        def get_user(self, token):
            if token == "valid":
                return FakeUserResponse(FakeUser("u1", "test@mail.com"))
            return FakeUserResponse(None)

        def sign_up(self, *_args, **_kwargs):
            return FakeAuthResponse(FakeUser("u1", "test@mail.com"), FakeSession("token123", 3600))

        def sign_in_with_password(self, *_args, **_kwargs):
            return FakeAuthResponse(FakeUser("u1", "test@mail.com"), FakeSession("token123", 3600))

        def reset_password_email(self, email):
            return {"ok": True}

        class admin:
            @staticmethod
            def delete_user(_user_id):
                return {"deleted": True}

    def table(self, name):
        # por defecto, retorna vacío si no está definido
        return FakeTableQuery(self._tables.get(name, []))


# ---------- TESTS ----------
def test_services_auth_import():
    service = AuthService()
    assert service is not None


def test_verify_supabase_token_valid(monkeypatch):
    from app.services import auth as auth_module

    fake = FakeSupabase()
    # tabla users devuelve rol
    fake._tables["users"] = [{"role": "manager"}]

    monkeypatch.setattr(auth_module, "supabase", fake)

    service = AuthService()
    payload = service.verify_supabase_token("valid")

    assert payload.sub == "u1"
    assert payload.email == "test@mail.com"
    assert payload.role == "manager"


def test_verify_supabase_token_invalid(monkeypatch):
    from app.services import auth as auth_module

    fake = FakeSupabase()
    monkeypatch.setattr(auth_module, "supabase", fake)

    service = AuthService()
    with pytest.raises(HTTPException) as e:
        service.verify_supabase_token("invalid")

    assert e.value.status_code == 401


@pytest.mark.asyncio
async def test_login_user_ok(monkeypatch):
    from app.services import auth as auth_module
    from app.models.auth import UserLogin

    fake = FakeSupabase()
    # tabla users devuelve el registro completo
    fake._tables["users"] = [{
        "id": "u1",
        "email": "test@mail.com",
        "role": "manager",
        "created_at": "2026-01-01T00:00:00+00:00",
        "updated_at": "2026-01-01T00:00:00+00:00",
    }]

    monkeypatch.setattr(auth_module, "supabase", fake)

    service = AuthService()
    res = await service.login_user(UserLogin(email="test@mail.com", password="123456"))

    assert res.access_token == "token123"
    assert res.user.email == "test@mail.com"
    assert res.user.role.value == "manager"