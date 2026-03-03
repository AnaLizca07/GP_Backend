from app.database import supabase


def test_database_connection_real():
    """
    SCRUM-87: Verifica que existe conexión real con Supabase.
    """

    response = supabase.table("users").select("id").limit(1).execute()

    assert response is not None
    assert hasattr(response, "data")