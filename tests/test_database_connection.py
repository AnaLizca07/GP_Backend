from unittest.mock import patch


def test_database_connection_mock():
    with patch("app.database.supabase") as mock_supabase:
        mock_supabase.table.return_value.select.return_value.execute.return_value.data = []

        response = mock_supabase.table("users").select("*").execute()

        assert response.data == []