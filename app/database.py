from supabase import create_client, Client
from app.config import settings
import logging

logger = logging.getLogger(__name__)

class SupabaseClient:
    _instance: Client = None

    @classmethod
    def get_client(cls) -> Client:
        """Obtener instancia singleton del cliente de Supabase"""
        if cls._instance is None:
            try:
                cls._instance = create_client(
                    settings.SUPABASE_URL,
                    settings.SUPABASE_KEY
                )
                logger.info("Cliente de Supabase inicializado correctamente")
            except Exception as e:
                logger.error(f"Error al inicializar cliente de Supabase: {e}")
                raise
        return cls._instance

# Instancia global del cliente
supabase: Client = SupabaseClient.get_client()