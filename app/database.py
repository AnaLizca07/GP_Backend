from supabase import create_client, Client
from app.config import settings
import logging

logger = logging.getLogger(__name__)

class SupabaseClient:
    _instance: Client = None
    _admin_instance: Client = None

    @classmethod
    def get_client(cls) -> Client:
        """Obtener instancia singleton del cliente de Supabase (anon key)"""
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

    @classmethod
    def get_admin_client(cls) -> Client:
        """Obtener cliente administrativo con service_role_key (opcional)"""
        if cls._admin_instance is None:
            try:
                # Usar service_role_key desde configuración
                service_role_key = settings.SUPABASE_SERVICE_ROLE_KEY

                if not service_role_key:
                    logger.warning("⚠️ SUPABASE_SERVICE_ROLE_KEY no encontrada. Usando cliente normal.")
                    return cls.get_client()

                cls._admin_instance = create_client(
                    settings.SUPABASE_URL,
                    service_role_key
                )
                logger.info("✅ Cliente administrativo de Supabase inicializado correctamente")
            except Exception as e:
                logger.error(f"Error al inicializar cliente administrativo: {e}")
                logger.warning("🔄 Fallback al cliente normal")
                return cls.get_client()
        return cls._admin_instance

# Instancia global del cliente (anon key)
supabase: Client = SupabaseClient.get_client()

# Cliente administrativo (opcional, solo si tienes service_role_key configurada)
def get_admin_supabase() -> Client:
    """Obtener cliente administrativo para operaciones especiales"""
    return SupabaseClient.get_admin_client()