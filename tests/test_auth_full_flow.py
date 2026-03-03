import pytest
from unittest.mock import patch, MagicMock
from app.services.auth import AuthService
from app.models.auth import UserRegister, UserLogin, UserRole


@pytest.mark.asyncio
async def test_full_auth_flow():
    service = AuthService()

    # Mock supabase
    with patch("app.services.auth.supabase") as mock_supabase:

        # Mock register
        mock_supabase.auth.sign_up.return_value = MagicMock(
            user=MagicMock(id="user123"),
            session=MagicMock(access_token="token123", expires_in=3600)
        )

        mock_supabase.table.return_value.insert.return_value.execute.return_value.data = [{
            "id": "user123"
        }]

        register_data = UserRegister(
            email="test@example.com",
            password="123456",
            role=UserRole.MANAGER
        )

        auth_response = await service.register_user(register_data)

        assert auth_response.access_token == "token123"
        assert auth_response.user.email == "test@example.com"

        # Mock login
        mock_supabase.auth.sign_in_with_password.return_value = MagicMock(
            user=MagicMock(id="user123"),
            session=MagicMock(access_token="token456", expires_in=3600)
        )

        mock_supabase.table.return_value.select.return_value.eq.return_value.execute.return_value.data = [{
            "id": "user123",
            "email": "test@example.com",
            "role": "manager",
            "created_at": "2024-01-01T00:00:00Z",
            "updated_at": "2024-01-01T00:00:00Z"
        }]

        login_data = UserLogin(
            email="test@example.com",
            password="123456"
        )

        login_response = await service.login_user(login_data)

        assert login_response.access_token == "token456"
        assert login_response.user.role.value == "manager"