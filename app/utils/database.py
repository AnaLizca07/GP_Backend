from supabase import create_client, Client
from app.config import settings

def get_supabase_client() -> Client:
    """
    Retorna cliente de Supabase
    """
    return create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)

# Cliente global
supabase: Client | None = None


def get_supabase():
    global supabase
    if supabase is None:
        supabase = get_supabase_client()
    return supabase