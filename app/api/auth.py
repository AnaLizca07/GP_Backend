from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Annotated

from app.models.auth import (
    UserRegister,
    UserLogin,
    UserResponse,
    AuthResponse,
    PasswordReset,
    EmployeeCreate,
    EmployeeResponse,
    ErrorResponse
)
from app.services.auth import auth_service

router = APIRouter()
security = HTTPBearer()

async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)]
) -> UserResponse:
    return await auth_service.get_current_user(credentials.credentials)

@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserRegister):
    """Registrar nuevo usuario"""
    return await auth_service.register_user(user_data)

@router.post("/login", response_model=AuthResponse)
async def login(login_data: UserLogin):
    """Iniciar sesión"""
    return await auth_service.login_user(login_data)

@router.get("/me", response_model=UserResponse)
async def get_profile(current_user: UserResponse = Depends(get_current_user)):
    """Obtener perfil del usuario actual"""
    return current_user

@router.post("/password-reset")
async def reset_password(reset_data: PasswordReset):
    """Enviar email de recuperación de contraseña"""
    return await auth_service.reset_password(reset_data.email)

@router.post("/employee-profile", response_model=EmployeeResponse, status_code=status.HTTP_201_CREATED)
async def create_employee_profile(
    employee_data: EmployeeCreate,
    current_user: UserResponse = Depends(get_current_user)
):
    """Crear perfil de empleado"""
    return await auth_service.create_employee_profile(employee_data, current_user)

@router.post("/logout")
async def logout():
    """Cerrar sesión"""
    return {"message": "Logged out successfully"}

@router.get("/validate-manager")
async def validate_manager_role(current_user: UserResponse = Depends(get_current_user)):
    """Validar rol de manager"""
    if current_user.role != "manager":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: Se requiere rol de manager"
        )
    return {"message": "Acceso autorizado", "role": "manager", "user_id": current_user.id}

@router.get("/validate-employee")
async def validate_employee_role(current_user: UserResponse = Depends(get_current_user)):
    """Validar rol de employee"""
    if current_user.role != "employee":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: Se requiere rol de employee"
        )
    return {"message": "Acceso autorizado", "role": "employee", "user_id": current_user.id}

@router.get("/validate-sponsor")
async def validate_sponsor_role(current_user: UserResponse = Depends(get_current_user)):
    """Validar rol de sponsor"""
    if current_user.role != "sponsor":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Acceso denegado: Se requiere rol de sponsor"
        )
    return {"message": "Acceso autorizado", "role": "sponsor", "user_id": current_user.id}

@router.get("/rate-limit-status")
async def get_rate_limit_status():
    """Obtener estado del rate limiting"""
    from app.services.rate_limit_handler import get_rate_limit_status
    return {
        "status": "ok",
        "rate_limiting": get_rate_limit_status()
    }