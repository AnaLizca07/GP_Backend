from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
import logging

from app.services.auth import auth_service
from app.models.auth import UserResponse

logger = logging.getLogger(__name__)

class AuthMiddleware:
    """Middleware personalizado para autenticación"""

    def __init__(self):
        self.security = HTTPBearer(auto_error=False)

    async def get_current_user_optional(self, request: Request) -> Optional[UserResponse]:
        """
        Obtener usuario actual de manera opcional (no falla si no hay token)
        Útil para endpoints que funcionan tanto con usuario autenticado como anónimo
        """
        try:
            authorization = request.headers.get("Authorization")
            if not authorization or not authorization.startswith("Bearer "):
                return None

            token = authorization.split(" ")[1]
            return await auth_service.get_current_user(token)
        except Exception as e:
            logger.debug(f"Token opcional inválido: {e}")
            return None

    async def require_role(self, request: Request, required_role: str) -> UserResponse:
        """
        Middleware que requiere un rol específico

        Args:
            request: Request de FastAPI
            required_role: Rol requerido ('manager', 'employee', 'sponsor')

        Returns:
            UserResponse: Usuario autenticado con el rol requerido

        Raises:
            HTTPException: Si no está autenticado o no tiene el rol requerido
        """
        try:
            authorization = request.headers.get("Authorization")
            if not authorization or not authorization.startswith("Bearer "):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token de autorización requerido",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            token = authorization.split(" ")[1]
            current_user = await auth_service.get_current_user(token)

            if current_user.role != required_role:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Acceso denegado: Se requiere rol '{required_role}', tienes '{current_user.role}'"
                )

            return current_user

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error en verificación de rol: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Error en autenticación",
                headers={"WWW-Authenticate": "Bearer"},
            )

    async def require_any_role(self, request: Request, allowed_roles: list[str]) -> UserResponse:
        """
        Middleware que requiere cualquiera de los roles especificados

        Args:
            request: Request de FastAPI
            allowed_roles: Lista de roles permitidos

        Returns:
            UserResponse: Usuario autenticado con alguno de los roles permitidos

        Raises:
            HTTPException: Si no está autenticado o no tiene ninguno de los roles permitidos
        """
        try:
            authorization = request.headers.get("Authorization")
            if not authorization or not authorization.startswith("Bearer "):
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token de autorización requerido",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            token = authorization.split(" ")[1]
            current_user = await auth_service.get_current_user(token)

            if current_user.role not in allowed_roles:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Acceso denegado: Se requiere uno de los roles {allowed_roles}, tienes '{current_user.role}'"
                )

            return current_user

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error en verificación de roles múltiples: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Error en autenticación",
                headers={"WWW-Authenticate": "Bearer"},
            )

# Instancia global del middleware
auth_middleware = AuthMiddleware()

# Funciones helper para usar como dependencias en FastAPI
async def require_manager(request: Request) -> UserResponse:
    """Dependencia que requiere rol de manager"""
    return await auth_middleware.require_role(request, "manager")

async def require_employee(request: Request) -> UserResponse:
    """Dependencia que requiere rol de employee"""
    return await auth_middleware.require_role(request, "employee")

async def require_sponsor(request: Request) -> UserResponse:
    """Dependencia que requiere rol de sponsor"""
    return await auth_middleware.require_role(request, "sponsor")

async def require_manager_or_employee(request: Request) -> UserResponse:
    """Dependencia que requiere rol de manager o employee"""
    return await auth_middleware.require_any_role(request, ["manager", "employee"])

async def require_any_authenticated(request: Request) -> UserResponse:
    """Dependencia que requiere cualquier usuario autenticado"""
    return await auth_middleware.require_any_role(request, ["manager", "employee", "sponsor"])

async def get_current_user_optional(request: Request) -> Optional[UserResponse]:
    """Dependencia opcional - devuelve usuario si está autenticado, None si no"""
    return await auth_middleware.get_current_user_optional(request)