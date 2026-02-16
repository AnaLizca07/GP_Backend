from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import logging
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status
from postgrest.exceptions import APIError

from app.database import supabase
from app.config import settings
from app.models.auth import (
    UserRegister,
    UserLogin,
    UserResponse,
    AuthResponse,
    TokenPayload,
    EmployeeCreate,
    EmployeeResponse
)

logger = logging.getLogger(__name__)

class AuthService:
    def __init__(self):
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        return self.pwd_context.verify(plain_password, hashed_password)

    def get_password_hash(self, password: str) -> str:
        return self.pwd_context.hash(password)

    def create_access_token(self, data: dict, expires_delta: Optional[timedelta] = None) -> str:
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
        return encoded_jwt

    def verify_token(self, token: str) -> TokenPayload:
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
            user_id: str = payload.get("sub")
            email: str = payload.get("email")
            role: str = payload.get("role")

            if user_id is None or email is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Token inválido",
                    headers={"WWW-Authenticate": "Bearer"},
                )

            return TokenPayload(sub=user_id, email=email, role=role)
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token inválido",
                headers={"WWW-Authenticate": "Bearer"},
            )

    async def register_user(self, user_data: UserRegister) -> AuthResponse:
        try:
            auth_response = supabase.auth.sign_up({
                "email": user_data.email,
                "password": user_data.password,
            })

            if not auth_response.user:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Error al crear usuario en Supabase Auth"
                )

            user_id = auth_response.user.id

            try:
                user_insert = supabase.table("users").insert({
                    "id": user_id,
                    "email": user_data.email,
                    "role": user_data.role.value,
                    "created_at": datetime.utcnow().isoformat(),
                    "updated_at": datetime.utcnow().isoformat()
                }).execute()

                if not user_insert.data:
                    supabase.auth.admin.delete_user(user_id)
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Error al crear perfil de usuario"
                    )

            except APIError as e:
                supabase.auth.admin.delete_user(user_id)
                if "duplicate key value" in str(e).lower():
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="El email ya está registrado"
                    )
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Error al crear usuario"
                )
            access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
            access_token = self.create_access_token(
                data={
                    "sub": user_id,
                    "email": user_data.email,
                    "role": user_data.role.value
                },
                expires_delta=access_token_expires
            )
            user_response = UserResponse(
                id=user_id,
                email=user_data.email,
                role=user_data.role,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )

            return AuthResponse(
                access_token=access_token,
                token_type="bearer",
                expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                user=user_response
            )

        except HTTPException:
            raise
        except Exception as e:
            from app.services.rate_limit_handler import handle_supabase_auth_error
            handle_supabase_auth_error(e, "register")

    async def login_user(self, login_data: UserLogin) -> AuthResponse:
        """Iniciar sesión de usuario"""
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

            # 3. Crear token de acceso personalizado (opcional, puedes usar el de Supabase)
            access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
            access_token = self.create_access_token(
                data={
                    "sub": user_id,
                    "email": user_data["email"],
                    "role": user_data["role"]
                },
                expires_delta=access_token_expires
            )

            # 4. Crear respuesta
            user_response = UserResponse(
                id=user_data["id"],
                email=user_data["email"],
                role=user_data["role"],
                created_at=datetime.fromisoformat(user_data["created_at"].replace('Z', '+00:00')),
                updated_at=datetime.fromisoformat(user_data["updated_at"].replace('Z', '+00:00')) if user_data["updated_at"] else None
            )

            # 5. Registrar login en audit_logs
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
                access_token=access_token,
                token_type="bearer",
                expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
                user=user_response
            )

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error en login de usuario: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error interno del servidor"
            )

    async def get_current_user(self, token: str) -> UserResponse:
        """Obtener usuario actual desde token"""
        token_data = self.verify_token(token)

        try:
            user_query = supabase.table("users").select("*").eq("id", token_data.sub).execute()

            if not user_query.data:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Usuario no encontrado"
                )

            user_data = user_query.data[0]

            return UserResponse(
                id=user_data["id"],
                email=user_data["email"],
                role=user_data["role"],
                created_at=datetime.fromisoformat(user_data["created_at"].replace('Z', '+00:00')),
                updated_at=datetime.fromisoformat(user_data["updated_at"].replace('Z', '+00:00')) if user_data["updated_at"] else None
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
            response = supabase.auth.reset_password_email(email)
            return {"message": "Email de recuperación enviado"}
        except Exception as e:
            logger.error(f"Error en reset de contraseña: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al enviar email de recuperación"
            )

    async def create_employee_profile(self, employee_data: EmployeeCreate, current_user: UserResponse) -> EmployeeResponse:
        """Crear perfil de empleado (solo para managers o el propio usuario)"""
        if current_user.role not in ["manager"] and current_user.id != employee_data.user_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tiene permisos para crear este perfil"
            )

        try:
            # Verificar que el user_id existe y tiene rol employee
            user_query = supabase.table("users").select("*").eq("id", employee_data.user_id).execute()
            if not user_query.data or user_query.data[0]["role"] != "employee":
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El usuario debe tener rol de empleado"
                )

            # Insertar perfil de empleado
            employee_insert = supabase.table("employees").insert({
                "user_id": employee_data.user_id,
                "name": employee_data.name,
                "identification": employee_data.identification,
                "position": employee_data.position,
                "phone": employee_data.phone,
                "address": employee_data.address,
                "salary_type": employee_data.salary_type,
                "salary_hourly": employee_data.salary_hourly,
                "salary_biweekly": employee_data.salary_biweekly,
                "salary_monthly": employee_data.salary_monthly,
                "resume_url": employee_data.resume_url,
                "status": employee_data.status,
                "created_at": datetime.utcnow().isoformat(),
                "updated_at": datetime.utcnow().isoformat()
            }).execute()

            if not employee_insert.data:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Error al crear perfil de empleado"
                )

            employee = employee_insert.data[0]

            return EmployeeResponse(
                id=employee["id"],
                user_id=employee["user_id"],
                name=employee["name"],
                identification=employee["identification"],
                position=employee["position"],
                phone=employee["phone"],
                address=employee["address"],
                salary_type=employee["salary_type"],
                salary_hourly=employee["salary_hourly"],
                salary_biweekly=employee["salary_biweekly"],
                salary_monthly=employee["salary_monthly"],
                resume_url=employee["resume_url"],
                status=employee["status"],
                created_at=datetime.fromisoformat(employee["created_at"].replace('Z', '+00:00')),
                updated_at=datetime.fromisoformat(employee["updated_at"].replace('Z', '+00:00')) if employee["updated_at"] else None
            )

        except HTTPException:
            raise
        except APIError as e:
            if "duplicate key value" in str(e).lower():
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="La identificación ya está registrada"
                )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error al crear perfil de empleado"
            )
        except Exception as e:
            logger.error(f"Error al crear perfil de empleado: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Error interno del servidor"
            )

# Instancia global del servicio
auth_service = AuthService()