"""
Dependencias compartidas de FastAPI para inyección en los routers.
Centraliza get_current_user y require_manager para evitar duplicación.
"""
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Annotated

from app.models.auth import UserResponse
from app.services.auth import auth_service

security = HTTPBearer()


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
) -> UserResponse:
    """Dependency: retorna el usuario autenticado a partir del Bearer token."""
    return await auth_service.get_current_user(credentials.credentials)


async def require_manager(
    current_user: UserResponse = Depends(get_current_user),
) -> UserResponse:
    """Dependency: requiere que el usuario autenticado sea gerente (manager)."""
    if current_user.role != "manager":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso restringido a gerentes",
        )
    return current_user
