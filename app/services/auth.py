from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging
from fastapi import HTTPException, status
from postgrest.exceptions import APIError

from app.database import supabase, get_admin_supabase
from app.models.auth import (
    UserRegister,
    UserLogin,
    UserResponse,
    AuthResponse,
    TokenPayload,
    UserRole
)
from app.services.notifications import notification_service

logger = logging.getLogger(__name__)

# Simple in-memory token cache to avoid Supabase round-trips on every request
_token_cache: Dict[str, tuple[TokenPayload, datetime]] = {}
_TOKEN_CACHE_TTL = timedelta(minutes=5)


def _get_cached_token(token: str) -> Optional[TokenPayload]:
    entry = _token_cache.get(token)
    if entry and datetime.utcnow() < entry[1]:
        return entry[0]
    if entry:
        del _token_cache[token]
    return None


def _cache_token(token: str, payload: TokenPayload) -> None:
    _token_cache[token] = (payload, datetime.utcnow() + _TOKEN_CACHE_TTL)
    # Evict old entries if cache grows too large
    if len(_token_cache) > 500:
        oldest = sorted(_token_cache.items(), key=lambda x: x[1][1])[:100]
        for k, _ in oldest:
            del _token_cache[k]


class AuthService:
    def __init__(self):
        pass

    def verify_supabase_token(self, token: str) -> TokenPayload:
        """Verificar token usando Supabase Auth (con caché local de 5 min)"""
        cached = _get_cached_token(token)
        if cached:
            return cached

        try:
            # Usar Supabase para obtener el usuario del token
            user_response = supabase.auth.get_user(token)

            if not user_response.user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token inválido",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            user_id = user_response.user.id
            email = user_response.user.email

            # Obtener el rol desde la tabla users
            user_query = supabase.table("users").select("role").eq("id", user_id).execute()
            role = user_query.data[0]["role"] if user_query.data else None

            # Leer must_change_password desde user_metadata de Supabase Auth
            user_metadata = user_response.user.user_metadata or {}
            must_change = bool(user_metadata.get("must_change_password", False))

            payload = TokenPayload(sub=user_id, email=email, role=role, must_change_password=must_change)
            _cache_token(token, payload)
            return payload
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error al verificar token: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido",
                headers={"WWW-Authenticate": "Bearer"},
            )

    async def register_user(self, user_data: UserRegister) -> AuthResponse:
        try:
            # Usar cliente administrativo para evitar "User not allowed"
            from app.database import get_admin_supabase
            admin_supabase = get_admin_supabase()

            logger.info(f"🔑 Registrando usuario: {user_data.email}")

            try:
                # Intentar con cliente administrativo primero
                auth_response = admin_supabase.auth.admin.create_user({
                    "email": user_data.email,
                    "password": user_data.password,
                    "email_confirm": True  # Confirmar email automáticamente
                })
                logger.info(f"✅ Usuario creado con cliente administrativo: {user_data.email}")

            except Exception as admin_error:
                logger.warning(f"❌ Error con cliente administrativo: {admin_error}")
                logger.info("🔄 Intentando con método normal como fallback...")

                # Fallback al método normal
                auth_response = supabase.auth.sign_up({
                    "email": user_data.email,
                    "password": user_data.password,
                })
                logger.info(f"✅ Usuario creado con método fallback: {user_data.email}")

            if not auth_response.user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Error al crear usuario en Supabase Auth"
                )

            user_id = auth_response.user.id

            try:
                # Usar cliente administrativo para insertar en tabla users también
                user_insert = admin_supabase.table("users").insert({
                    "id": user_id,
                    "email": user_data.email,
                    "role": user_data.role.value,
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat()
                }).execute()

                if not user_insert.data:
                    admin_supabase.auth.admin.delete_user(user_id)
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Error al crear perfil de usuario"
                    )

            except APIError as e:
                admin_supabase.auth.admin.delete_user(user_id)
                if "duplicate key value" in str(e).lower():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="El email ya está registrado"
                    )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Error al crear usuario"
                )

            # Usar el token de Supabase directamente
            user_response = UserResponse(
                id=user_id,
                email=user_data.email,
                role=user_data.role,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )

            # Para admin.create_user(), necesitamos hacer login después para obtener token
            # o generar un token temporal
            access_token = ""
            expires_in = 3600

            # Si tenemos una sesión (método fallback), usar su token
            if hasattr(auth_response, 'session') and auth_response.session:
                access_token = auth_response.session.access_token
                expires_in = auth_response.session.expires_in
                logger.info("🔑 Usando token de sesión normal")
            else:
                # Para método administrativo, hacer login automático para generar token
                # IMPORTANTE: usar el cliente anon (supabase), no el admin singleton,
                # para evitar contaminar la sesión del cliente con service_role_key.
                try:
                    login_response = supabase.auth.sign_in_with_password({
                        "email": user_data.email,
                        "password": user_data.password
                    })
                    if login_response.session:
                        access_token = login_response.session.access_token
                        expires_in = login_response.session.expires_in
                        logger.info("🔑 Token generado mediante login automático")
                except Exception as login_error:
                    logger.warning(f"No se pudo generar token automáticamente: {login_error}")
                    # Continuar sin token, el usuario deberá hacer login manualmente

            return AuthResponse(
                access_token=access_token,
                token_type="bearer",
                expires_in=expires_in,
                user=user_response
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error en registro de usuario: {e}")
            from app.services.rate_limit_handler import handle_supabase_auth_error
            handle_supabase_auth_error(e, "register")
            # Si handle_supabase_auth_error no lanza excepción, lanzar error genérico
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error interno del servidor"
            )

    async def login_user(self, login_data: UserLogin) -> AuthResponse:
        """Iniciar sesión de usuario usando Supabase Auth"""
        try:
            # 1. Autenticar con Supabase Auth
            auth_response = supabase.auth.sign_in_with_password({
                "email": login_data.email,
                "password": login_data.password
            })

            if not auth_response.user or not auth_response.session:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Credenciales incorrectas"
                )

            user_id = auth_response.user.id

            # 2. Obtener datos del usuario de la tabla users
            user_query = supabase.table("users").select("*").eq("id", user_id).execute()

            if not user_query.data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Usuario no encontrado en base de datos"
                )

            user_data = user_query.data[0]

            # 3. Crear respuesta usando el token de Supabase
            # Leer must_change_password desde user_metadata de Supabase Auth
            user_meta = auth_response.user.user_metadata or {}
            must_change = bool(user_meta.get("must_change_password", False))

            user_response = UserResponse(
                id=user_data["id"],
                email=user_data["email"],
                role=UserRole(user_data["role"]),
                created_at=datetime.fromisoformat(user_data["created_at"].replace('Z', '+00:00')),
                updated_at=datetime.fromisoformat(user_data["updated_at"].replace('Z', '+00:00')) if user_data["updated_at"] else None,
                must_change_password=must_change,
            )

            # 4. Registrar login en audit_logs
            try:
                supabase.table("audit_logs").insert({
                    "user_id": user_id,
                    "action": "LOGIN",
                    "table_name": "users",
                    "record_id": None,
                    "old_data": None,
                    "new_data": {"login_time": datetime.utcnow().isoformat()},
                    "created_at": datetime.utcnow().isoformat()
                }).execute()
            except Exception as e:
                logger.warning(f"Error al registrar login en audit: {e}")

            return AuthResponse(
                access_token=auth_response.session.access_token,
                token_type="bearer",
                expires_in=auth_response.session.expires_in,
                user=user_response
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error en login de usuario: {e}")
            from app.services.rate_limit_handler import handle_supabase_auth_error
            handle_supabase_auth_error(e, "login")
            # Si handle_supabase_auth_error no lanza excepción, lanzar error genérico
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error interno del servidor"
            )

    async def get_current_user(self, token: str) -> UserResponse:
        """Obtener usuario actual desde token usando Supabase Auth"""
        token_data = self.verify_supabase_token(token)

        try:
            # Usar cliente administrativo para validar usuarios
            from app.database import get_admin_supabase
            admin_client = get_admin_supabase()

            user_query = admin_client.table("users").select("*").eq("id", token_data.sub).execute()

            if not user_query.data:
                # El usuario existe en Supabase Auth pero no en tabla users
                # Crear registro en tabla users automáticamente
                try:
                    default_role = "sponsor"

                    # Si el email contiene indicadores, ajustar el rol
                    if token_data.email:
                        if "@manager" in token_data.email.lower() or "admin" in token_data.email.lower():
                            default_role = "manager"
                        elif "employee" in token_data.email.lower():
                            default_role = "employee"

                    user_insert = admin_client.table("users").insert({
                        "id": token_data.sub,
                        "email": token_data.email,
                        "role": default_role,
                        "created_at": datetime.utcnow().isoformat(),
                        "updated_at": datetime.utcnow().isoformat()
                    }).execute()

                    if user_insert.data:
                        user_data = user_insert.data[0]
                    else:
                        raise Exception("No se pudo insertar usuario en tabla users")

                except Exception as insert_error:
                    logger.error(f"Error al crear usuario en tabla users: {insert_error}")

                    # Verificar si es un error de permisos
                    if "permission" in str(insert_error).lower() or "forbidden" in str(insert_error).lower():
                        detail_msg = "Error de permisos al crear usuario en tabla. Verifique configuración de Supabase."
                    elif "duplicate key" in str(insert_error).lower():
                        detail_msg = "Usuario ya existe en tabla pero no se pudo recuperar."
                    else:
                        detail_msg = f"Error al sincronizar usuario: {str(insert_error)}"

                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail=detail_msg
                    )
            else:
                user_data = user_query.data[0]

            return UserResponse(
                id=user_data["id"],
                email=user_data["email"],
                role=UserRole(user_data["role"]),
                created_at=datetime.fromisoformat(user_data["created_at"].replace('Z', '+00:00')),
                updated_at=datetime.fromisoformat(user_data["updated_at"].replace('Z', '+00:00')) if user_data["updated_at"] else None,
                must_change_password=token_data.must_change_password,
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error al obtener usuario actual: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error interno del servidor"
            )

    async def reset_password(self, email: str) -> dict:
        """Enviar email de reset de contraseña"""
        try:
            response = supabase.auth.reset_password_email(
                email,
                {"redirect_to": "https://gp-frontend-ebon.vercel.app/reset-password"}
            )
            return {"message": "Email de recuperación enviado"}
        except Exception as e:
            logger.error(f"Error en reset de contraseña: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al enviar email de recuperación"
            )

    async def change_password(self, new_password: str, current_user: UserResponse) -> dict:
        """
        Cambiar contraseña del usuario actual

        - Valida fortaleza de la nueva contraseña
        - Actualiza la contraseña en Supabase Auth
        - Marca como False el flag must_change_password
        """
        try:
            # 1. Validar fortaleza de la nueva contraseña
            password_validation = notification_service.validate_password_strength(new_password)

            if not password_validation['is_valid']:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail={
                        "message": "La contraseña no cumple con los requisitos de seguridad",
                        "suggestions": password_validation['suggestions'],
                        "strength": password_validation['strength']
                    }
                )

            # 2. Actualizar contraseña Y limpiar must_change_password via admin client
            from app.database import get_admin_supabase
            admin_client = get_admin_supabase()

            user_update_response = admin_client.auth.admin.update_user_by_id(
                current_user.id,
                {
                    "password": new_password,
                    "user_metadata": {"must_change_password": False},
                }
            )

            if not user_update_response.user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Error al actualizar contraseña en Supabase Auth"
                )

            # 3. Actualizar timestamp en tabla users
            admin_client.table("users").update({
                "updated_at": datetime.utcnow().isoformat()
            }).eq("id", current_user.id).execute()

            # 4. Invalidar caché del token para este usuario (flag ya no aplica)
            for token_key in list(_token_cache.keys()):
                if _token_cache[token_key][0].sub == current_user.id:
                    del _token_cache[token_key]

            # 5. Log de auditoría
            try:
                admin_client.table("audit_logs").insert({
                    "user_id": current_user.id,
                    "action": "PASSWORD_CHANGE",
                    "table_name": "users",
                    "record_id": None,
                    "old_data": {"must_change_password": True},
                    "new_data": {"must_change_password": False, "password_changed": True},
                    "created_at": datetime.utcnow().isoformat()
                }).execute()
            except Exception as audit_error:
                logger.warning(f"Error en log de auditoría: {audit_error}")

            logger.info(f"🔑 Contraseña cambiada exitosamente para usuario {current_user.email}")

            return {
                "message": "Contraseña actualizada exitosamente",
                "password_strength": password_validation['strength'],
                "must_change_password": False,
            }

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error al cambiar contraseña: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error interno del servidor"
            )


# Instancia global del servicio
auth_service = AuthService()